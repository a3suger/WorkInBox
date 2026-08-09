from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

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
4. deadline と schedule が false で、返信・回答・承認・意思表示など相手への応答が必要、または合理的に必要と考えられるなら answer_required=true。これも再現率を重視してください。
5. 上記に該当しないが、内容を読んで検討・確認する必要がある場合は review=true。
6. 本文欠損、強い文脈依存、添付を確認しないと判断不能など、分類に必要な材料そのものが不足している場合だけ pending=true。通常の曖昧さでは pending にしないでください。

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


class OllamaClassifier:
    def __init__(self, config: AiConfig) -> None:
        self.config = config

    def classify(self, message: EmailMessage) -> AiClassification:
        body = (message.body or "")[: self.config.body_max_chars]
        prompt = (
            f"件名: {message.subject or '(件名なし)'}\n"
            f"差出人: {message.sender}\n"
            f"宛先: {message.recipients or '(不明)'}\n"
            f"本文（先頭最大 {self.config.body_max_chars} 文字）:\n"
            f"{body}"
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
