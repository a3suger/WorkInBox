from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from workinbox.config import AiConfig
from workinbox.models import EmailMessage
from workinbox.record_summarizer import OllamaRecordSummarizer


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps({"response": "重要な決定事項の要約"}).encode("utf-8")


class RecordSummarizerTest(unittest.TestCase):
    def test_summarizes_source_email_with_configured_ollama(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        message = EmailMessage(
            "<source@example>", "sender@example.com", "me@example.com",
            "元メール", None, "残しておくべき本文\n> 過去の引用",
        )
        summarizer = OllamaRecordSummarizer(AiConfig(body_max_chars=100, timeout_seconds=45))

        with patch("workinbox.record_summarizer.urllib.request.urlopen", fake_urlopen):
            result = summarizer.summarize(message)

        self.assertEqual(result, "重要な決定事項の要約")
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/api/generate")
        self.assertEqual(captured["timeout"], 45)
        self.assertIn("残しておくべき本文", captured["body"]["prompt"])
        self.assertNotIn("過去の引用", captured["body"]["prompt"])


if __name__ == "__main__":
    unittest.main()
