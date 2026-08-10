from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.utils import getaddresses

from .config import AiConfig
from .models import EmailMessage


CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "deadline": {"type": "boolean"},
        "schedule": {"type": "boolean"},
        "answer_required": {"type": "boolean"},
        "review": {"type": "boolean"},
        "pending": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": [
        "deadline",
        "schedule",
        "answer_required",
        "review",
        "pending",
        "reason",
    ],
    "additionalProperties": False,
}


SYSTEM_PROMPT = """あなたは WorkInBox のメール初期分類器です。
このメールはすでに利用者がスターを付けており、何らかの確認または対応が必要なメールです。
メールを追跡対象にする価値があるかどうかは再判定しないでください。

次の順序で分類してください。
1. 締切・提出期限・回答期限・手続期限など、特定日時までの対応が必要、または合理的に必要と考えられるなら deadline=true。見逃しを避けるため再現率を重視してください。
2. 会議、面談、訪問、日程候補、日時調整、参加可否などのスケジュール調整が必要なら schedule=true。deadline と同時に true でも構いません。見逃しを避けるため再現率を重視してください。
3. deadline または schedule が true の場合、answer_required と review は false にしてください。
4. deadline と schedule が false で、返信・回答・承認・意思表示など利用者から相手への追加の応答が必要、または合理的に必要と考えられるなら answer_required=true。これも再現率を重視してください。
5. 差出人が利用者本人の場合、すでに送信済みであること自体を理由に answer_required=true にしないでください。利用者側に追加の回答、追送、承認、手続などが必要な場合だけ answer_required=true にしてください。相手からの返信待ちかどうかの判定はこの初期分類の責務ではありません。
6. 上記に該当しないが、内容を読んで検討・確認する必要がある場合は review=true。
7. 本文欠損、強い文脈依存、添付を確認しないと判断不能など、分類に必要な材料そのものが不足している場合だけ pending=true。通常の曖昧さでは pending にしないでください。

本人判定ではメールアドレスを主情報とし、利用者名は本文中の署名・呼びかけ等を理解するための補助情報として扱ってください。名前だけを根拠に本人と断定しないでください。

JSON Schema に従う JSON だけを返してください。reason は短い日本語で記述してください。"""


@dataclass(frozen=True, slots=True)
class AiClassification:
    deadline: bool
    schedule: bool
    answer_required: bool
    review: bool
    pending: bool
    reason: str

    def tag_keys(self) -> tuple[str, ...]:
        if self.deadline or self.schedule:
            keys: list[str] = []
            if self.deadline:
                keys.append("wib-deadline")
            if self.schedule:
                keys.append("wib-schedule")
            return tuple(keys)
        if self.answer_required:
            return ("wib-answer",)
        if self.review:
            return ("wib-review",)
        if self.pending:
            return ("wib-pending",)
        return ("wib-review",)


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
        body = (message.body or "")[: self.config.body_max_chars]
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
            + f"本文（先頭最大 {self.config.body_max_chars} 文字）:\n"
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

        required = (
            "deadline",
            "schedule",
            "answer_required",
            "review",
            "pending",
        )
        if any(type(result.get(name)) is not bool for name in required):
            raise RuntimeError("Ollama classification booleans are invalid")
        reason = result.get("reason")
        if not isinstance(reason, str):
            raise RuntimeError("Ollama classification reason is invalid")

        return AiClassification(
            deadline=result["deadline"],
            schedule=result["schedule"],
            answer_required=result["answer_required"],
            review=result["review"],
            pending=result["pending"],
            reason=reason,
        )
