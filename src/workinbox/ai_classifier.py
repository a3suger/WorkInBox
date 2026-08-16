from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.utils import getaddresses
from enum import StrEnum

from .config import AiConfig
from .models import EmailMessage


class NormalWorkflow(StrEnum):
    ANSWER = "answer"
    REVIEW = "review"
    WATCH = "watch"
    NONE = "none"
    PENDING = "pending"


CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "deadline": {"type": "boolean"},
        "schedule": {"type": "boolean"},
        "normal_workflow": {
            "type": "string",
            "enum": [workflow.value for workflow in NormalWorkflow],
        },
        "reason": {"type": "string"},
    },
    "required": ["deadline", "schedule", "normal_workflow", "reason"],
    "additionalProperties": False,
}


SYSTEM_PROMPT = """あなたは WorkInBox のメール初期分類器です。
このメールはすでに利用者がスターを付けており、何らかの確認または対応が必要なメールです。
メールを追跡対象にする価値があるかどうかは再判定しないでください。

専用ワークフローと通常ワークフローを独立して判定してください。

専用ワークフロー:
1. 締切・提出期限・回答期限・手続期限など、特定日時までの対応が必要、または合理的に必要と考えられるなら deadline=true。見逃しを避けるため再現率を重視してください。
2. 会議、面談、訪問、日程候補、日時調整、参加可否などのスケジュール調整が必要なら schedule=true。deadline と同時に true でも構いません。
3. deadline または schedule が true でも、通常ワークフローの判定を省略しないでください。

通常ワークフローは normal_workflow に次のどれか1つを返してください。
- answer: 対象メールの相手に返信・回答・承認・意思表示などを返す必要がある。
- review: 対象メールへの返信は不要だが、内容を読み、検討・確認する必要がある。
- watch: 自分から直ちに返信・処理する必要はないが、そのスレッドの今後の進展を継続して確認する必要がある。
- none: 今後の返信・検討・継続確認はいずれも不要である。
- pending: 通常ワークフローを判断するための材料そのものが不足している。本文欠損、強い文脈依存、添付を確認しないと判断不能などの場合だけ使い、通常の曖昧さでは使わない。

差出人が利用者本人の場合、すでに送信済みであること自体を理由に answer にしないでください。利用者側に追加の回答、追送、承認、手続などが必要な場合だけ answer にしてください。相手からの返信待ちかどうかの判定はこの初期分類の責務ではありません。

本人判定ではメールアドレスを主情報とし、利用者名は本文中の署名・呼びかけ等を理解するための補助情報として扱ってください。名前だけを根拠に本人と断定しないでください。

JSON Schema に従う JSON だけを返してください。reason は短い日本語で記述してください。"""


_REPLY_SEPARATOR_RE = re.compile(
    r"^(?:On .+ wrote:|-----Original Message-----|-{2,}\s*Original Message\s*-{2,})$",
    re.IGNORECASE,
)
_SIGNATURE_RE = re.compile(r"^--\s*$")


def preprocess_body(body: str | None, max_chars: int) -> str:
    """Best-effort extraction of newly written text before applying the limit."""
    if not body:
        return ""

    kept: list[str] = []
    for raw_line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.rstrip()
        stripped = line.strip()
        if _REPLY_SEPARATOR_RE.match(stripped) or _SIGNATURE_RE.match(stripped):
            break
        if stripped.startswith(">"):
            continue
        kept.append(line)

    text = "\n".join(kept).strip()
    return text[:max_chars]


@dataclass(frozen=True, slots=True)
class AiClassification:
    deadline: bool
    schedule: bool
    normal_workflow: NormalWorkflow
    reason: str

    def tag_keys(self) -> tuple[str, ...]:
        keys: list[str] = []
        if self.deadline:
            keys.append("wib-deadline")
        if self.schedule:
            keys.append("wib-schedule")

        normal_key = {
            NormalWorkflow.ANSWER: "wib-answer",
            NormalWorkflow.REVIEW: "wib-review",
            NormalWorkflow.WATCH: "wib-watch",
        }.get(self.normal_workflow)
        if normal_key is not None:
            keys.append(normal_key)
        elif not (self.deadline or self.schedule):
            if self.normal_workflow == NormalWorkflow.PENDING:
                keys.append("wib-pending")
            elif self.normal_workflow == NormalWorkflow.NONE:
                keys.append("wib-bulk")
        return tuple(keys)

    def should_unstar(self) -> bool:
        return (
            not self.deadline
            and not self.schedule
            and self.normal_workflow == NormalWorkflow.NONE
        )


def _addresses(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        address.strip().lower()
        for _name, address in getaddresses([value])
        if address.strip()
    }


class OllamaClassifier:
    def __init__(self, config: AiConfig) -> None:
        self.config = config

    def classify(self, message: EmailMessage) -> AiClassification:
        body = preprocess_body(message.body, self.config.body_max_chars)
        identity = self.config.identity
        self_addresses = set(identity.all_addresses) if identity is not None else set()
        sender_addresses = _addresses(message.sender)
        recipient_addresses = _addresses(message.recipients)
        is_from_self = bool(self_addresses.intersection(sender_addresses))
        is_to_self = bool(self_addresses.intersection(recipient_addresses))

        identity_lines = [
            f"差出人は利用者本人: {'true' if is_from_self else 'false'}",
            f"宛先に利用者本人を含む: {'true' if is_to_self else 'false'}",
        ]
        if identity is not None:
            identity_lines.insert(
                0,
                "利用者本人のメールアドレス: " + ", ".join(identity.all_addresses),
            )
            if identity.name:
                identity_lines.insert(0, f"利用者名（補助情報）: {identity.name}")
        else:
            identity_lines.insert(0, "利用者本人のメールアドレス: 未設定")

        prompt = (
            "\n".join(identity_lines)
            + "\n"
            + f"件名: {message.subject or '(件名なし)'}\n"
            + f"差出人: {message.sender}\n"
            + f"宛先: {message.recipients or '(不明)'}\n"
            + f"本文（引用等の前処理後、最大 {self.config.body_max_chars} 文字）:\n"
            + body
        )
        request_body = json.dumps(
            {
                "model": self.config.model,
                "system": SYSTEM_PROMPT,
                "prompt": prompt,
                "stream": False,
                "format": CLASSIFICATION_SCHEMA,
                "keep_alive": self.config.keep_alive,
                "options": {"temperature": 0},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.config.url.rstrip("/") + "/api/generate",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        raw_response = payload.get("response")
        if not isinstance(raw_response, str):
            raise RuntimeError("Ollama response does not contain a JSON response string")
        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid classification JSON") from exc

        if type(result.get("deadline")) is not bool or type(result.get("schedule")) is not bool:
            raise RuntimeError("Ollama classification booleans are invalid")
        try:
            normal_workflow = NormalWorkflow(result.get("normal_workflow"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Ollama normal workflow classification is invalid") from exc
        reason = result.get("reason")
        if not isinstance(reason, str):
            raise RuntimeError("Ollama classification reason is invalid")

        return AiClassification(
            deadline=result["deadline"],
            schedule=result["schedule"],
            normal_workflow=normal_workflow,
            reason=reason,
        )
