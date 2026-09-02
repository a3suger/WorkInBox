from __future__ import annotations

import json
import urllib.error
import urllib.request

from .ai_classifier import preprocess_body
from .config import AiConfig
from .models import EmailMessage


class OllamaRecordSummarizer:
    def __init__(self, config: AiConfig) -> None:
        self.config = config

    def summarize(self, message: EmailMessage) -> str:
        prompt = (
            f"件名: {message.subject or '(件名なし)'}\n"
            f"差出人: {message.sender}\n"
            f"本文:\n{preprocess_body(message.body, self.config.body_max_chars)}"
        )
        body = json.dumps({
            "model": self.config.model,
            "system": "Recordとして後から参照できるよう、このメールの要点を簡潔な日本語で要約してください。要約本文だけを返してください。",
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.config.keep_alive,
            "options": {"temperature": 0},
        }).encode("utf-8")
        request = urllib.request.Request(
            self.config.url.rstrip("/") + "/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama Record summary failed: {exc}") from exc
        summary = payload.get("response")
        if not isinstance(summary, str) or not summary.strip():
            raise RuntimeError("Ollama returned an empty Record summary")
        return summary.strip()
