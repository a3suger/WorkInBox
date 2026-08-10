from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import AiConfig
from .models import EmailMessage


DEADLINE_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "deadlines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "due_at": {"type": ["string", "null"]},
                    "source_text": {"type": ["string", "null"]},
                    "needs_review": {"type": "boolean"},
                },
                "required": ["title", "due_at", "source_text", "needs_review"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["deadlines"],
    "additionalProperties": False,
}


DEADLINE_EXTRACTION_SYSTEM_PROMPT = """あなたは WorkInBox の締切候補抽出器です。
このメールにはすでに `締切あり` と判定されています。
メール本文から、利用者が WorkInBox に登録して確認すべき締切候補を 0 件以上抽出してください。

ルール:
- 1 通のメールに複数の締切があれば、意味ごとに別候補として抽出してください。
- 同じ締切が本文中で繰り返されているだけなら重複候補を作らないでください。
- title は「何の締切か」が分かる短い日本語にしてください。
- due_at は、日付だけなら YYYY-MM-DD、時刻まで明示されていれば ISO 8601 形式を基本にしてください。
- 年が省略されている場合は、メール受信日時以後に到来する最初の該当日付として補完してください。
- 日付を特定できない締切も捨てず、due_at=null の候補として残してください。
- source_text は判断根拠となった本文の短い抜粋にしてください。根拠箇所が明確でなければ null でも構いません。
- 日付や意味に推定・曖昧さがある場合、または due_at=null の場合は needs_review=true にしてください。
- 単なる予定・開催日時ではなく、利用者が何かを完了すべき期限を締切として抽出してください。
- 抽出すべき締切が見つからなければ deadlines=[] を返してください。

JSON Schema に従う JSON だけを返してください。"""


@dataclass(frozen=True, slots=True)
class ExtractedDeadlineCandidate:
    title: str
    due_at: str | None
    source_text: str | None
    needs_review: bool


class OllamaDeadlineExtractor:
    def __init__(self, config: AiConfig) -> None:
        self.config = config

    def extract(self, message: EmailMessage) -> tuple[ExtractedDeadlineCandidate, ...]:
        body = (message.body or "")[: self.config.body_max_chars]
        prompt = (
            f"メール受信日時: {message.received_at or '(不明)'}\n"
            f"件名: {message.subject or '(件名なし)'}\n"
            f"差出人: {message.sender}\n"
            f"宛先: {message.recipients or '(不明)'}\n"
            f"本文（先頭最大 {self.config.body_max_chars} 文字）:\n"
            f"{body}"
        )
        request_body = json.dumps(
            {
                "model": self.config.model,
                "system": DEADLINE_EXTRACTION_SYSTEM_PROMPT,
                "prompt": prompt,
                "stream": False,
                "format": DEADLINE_EXTRACTION_SCHEMA,
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
            raise RuntimeError(f"Ollama deadline extraction failed: {exc}") from exc

        raw_response = payload.get("response")
        if not isinstance(raw_response, str):
            raise RuntimeError("Ollama response does not contain a JSON response string")
        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid deadline extraction JSON") from exc

        deadlines = result.get("deadlines")
        if not isinstance(deadlines, list):
            raise RuntimeError("Ollama deadline extraction result is invalid")

        extracted: list[ExtractedDeadlineCandidate] = []
        seen: set[tuple[str, str | None, str | None]] = set()
        for item in deadlines:
            if not isinstance(item, dict):
                raise RuntimeError("Ollama deadline candidate is invalid")
            title = item.get("title")
            due_at = item.get("due_at")
            source_text = item.get("source_text")
            needs_review = item.get("needs_review")
            if not isinstance(title, str) or not title.strip():
                raise RuntimeError("Ollama deadline candidate title is invalid")
            if due_at is not None and not isinstance(due_at, str):
                raise RuntimeError("Ollama deadline candidate due_at is invalid")
            if source_text is not None and not isinstance(source_text, str):
                raise RuntimeError("Ollama deadline candidate source_text is invalid")
            if type(needs_review) is not bool:
                raise RuntimeError("Ollama deadline candidate needs_review is invalid")

            normalized = (
                title.strip(),
                due_at.strip() if isinstance(due_at, str) and due_at.strip() else None,
                source_text.strip()
                if isinstance(source_text, str) and source_text.strip()
                else None,
            )
            if normalized in seen:
                continue
            seen.add(normalized)
            extracted.append(
                ExtractedDeadlineCandidate(
                    title=normalized[0],
                    due_at=normalized[1],
                    source_text=normalized[2],
                    needs_review=needs_review or normalized[1] is None,
                )
            )
        return tuple(extracted)
