from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from workinbox.ai_classifier import AiClassification, OllamaClassifier
from workinbox.config import AiConfig
from workinbox.models import EmailMessage


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class OllamaClassifierTest(unittest.TestCase):
    def test_classify_uses_structured_json_and_truncates_body(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            response = {
                "deadline": True,
                "schedule": False,
                "answer_required": False,
                "review": False,
                "pending": False,
                "reason": "期限がある",
            }
            return FakeResponse({"response": json.dumps(response)})

        message = EmailMessage(
            "<1@example>",
            "sender@example.com",
            "me@example.com",
            "Subject",
            None,
            "abcdefghij",
        )
        classifier = OllamaClassifier(
            AiConfig(
                url="http://127.0.0.1:11434",
                model="qwen2.5:7b",
                body_max_chars=5,
                timeout_seconds=30,
            )
        )

        with patch("workinbox.ai_classifier.urllib.request.urlopen", fake_urlopen):
            result = classifier.classify(message)

        self.assertEqual(result.tag_keys(), ("wib-deadline",))
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/api/generate")
        self.assertEqual(captured["timeout"], 30)
        request_body = captured["body"]
        self.assertEqual(request_body["model"], "qwen2.5:7b")
        self.assertFalse(request_body["stream"])
        self.assertIsInstance(request_body["format"], dict)
        self.assertIn("abcde", request_body["prompt"])
        self.assertNotIn("abcdef", request_body["prompt"])

    def test_tag_keys_enforce_allowed_combinations(self) -> None:
        self.assertEqual(
            AiClassification(True, True, True, True, True, "x").tag_keys(),
            ("wib-deadline", "wib-schedule"),
        )
        self.assertEqual(
            AiClassification(False, False, True, True, True, "x").tag_keys(),
            ("wib-answer",),
        )
        self.assertEqual(
            AiClassification(False, False, False, True, True, "x").tag_keys(),
            ("wib-review",),
        )
        self.assertEqual(
            AiClassification(False, False, False, False, True, "x").tag_keys(),
            ("wib-pending",),
        )

    def test_no_true_value_falls_back_to_review(self) -> None:
        result = AiClassification(False, False, False, False, False, "x")
        self.assertEqual(result.tag_keys(), ("wib-review",))


if __name__ == "__main__":
    unittest.main()
