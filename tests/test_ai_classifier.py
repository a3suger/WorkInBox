from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from workinbox.ai_classifier import (
    AiClassification,
    NormalWorkflow,
    OllamaClassifier,
    preprocess_body,
)
from workinbox.config import AiConfig, IdentityConfig
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
    def test_classify_uses_structured_json_preprocesses_body_and_keeps_model_alive(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            response = {
                "deadline": True,
                "schedule": False,
                "normal_workflow": "answer",
                "reason": "期限があり返信も必要",
            }
            return FakeResponse({"response": json.dumps(response)})

        message = EmailMessage(
            "<1@example>",
            "sender@example.com",
            "me@example.com",
            "Subject",
            None,
            "abcdef\n> quoted old text\n-----Original Message-----\nold body",
        )
        classifier = OllamaClassifier(
            AiConfig(
                url="http://127.0.0.1:11434",
                model="qwen2.5:7b",
                body_max_chars=5,
                timeout_seconds=30,
                keep_alive="15m",
                max_workers=2,
            )
        )

        with patch("workinbox.ai_classifier.urllib.request.urlopen", fake_urlopen):
            result = classifier.classify(message)

        self.assertEqual(result.tag_keys(), ("wib-deadline", "wib-answer"))
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/api/generate")
        self.assertEqual(captured["timeout"], 30)
        request_body = captured["body"]
        self.assertEqual(request_body["model"], "qwen2.5:7b")
        self.assertEqual(request_body["keep_alive"], "15m")
        self.assertFalse(request_body["stream"])
        self.assertIsInstance(request_body["format"], dict)
        self.assertIn("abcde", request_body["prompt"])
        self.assertNotIn("abcdef", request_body["prompt"])
        self.assertNotIn("quoted old text", request_body["prompt"])
        self.assertNotIn("old body", request_body["prompt"])

    def test_classify_adds_identity_context_and_detects_self_sender(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            response = {
                "deadline": False,
                "schedule": False,
                "normal_workflow": "review",
                "reason": "送信済みメールの確認",
            }
            return FakeResponse({"response": json.dumps(response)})

        message = EmailMessage(
            "<self@example>",
            'Example User <Alias@Example.COM>',
            "recipient@example.net",
            "Follow up",
            None,
            "本文",
        )
        classifier = OllamaClassifier(
            AiConfig(
                identity=IdentityConfig(
                    mailbox_address="main@example.com",
                    self_addresses=("alias@example.com",),
                    name="Example User",
                )
            )
        )

        with patch("workinbox.ai_classifier.urllib.request.urlopen", fake_urlopen):
            classifier.classify(message)

        prompt = captured["body"]["prompt"]
        self.assertIn("利用者名（補助情報）: Example User", prompt)
        self.assertIn("main@example.com, alias@example.com", prompt)
        self.assertIn("差出人は利用者本人: true", prompt)
        self.assertIn("宛先に利用者本人を含む: false", prompt)

    def test_dedicated_and_normal_workflow_can_coexist(self) -> None:
        result = AiClassification(
            True,
            True,
            reason="期限付き日程調整で返信も必要",
            normal_workflow=NormalWorkflow.ANSWER,
        )
        self.assertEqual(
            result.tag_keys(),
            ("wib-deadline", "wib-schedule", "wib-answer"),
        )
        self.assertFalse(result.should_unstar())

    def test_normal_workflow_supports_review_and_watch(self) -> None:
        self.assertEqual(
            AiClassification(False, False, normal_workflow="review").tag_keys(),
            ("wib-review",),
        )
        self.assertEqual(
            AiClassification(False, False, normal_workflow="watch").tag_keys(),
            ("wib-watch",),
        )

    def test_pending_is_only_emitted_without_dedicated_workflow(self) -> None:
        self.assertEqual(
            AiClassification(False, False, normal_workflow="pending").tag_keys(),
            ("wib-pending",),
        )
        self.assertEqual(
            AiClassification(True, False, normal_workflow="pending").tag_keys(),
            ("wib-deadline",),
        )

    def test_nothing_to_do_becomes_bulk_and_requests_unstar(self) -> None:
        result = AiClassification(False, False, normal_workflow="none")
        self.assertEqual(result.tag_keys(), ("wib-bulk",))
        self.assertTrue(result.should_unstar())

        dedicated = AiClassification(True, False, normal_workflow="none")
        self.assertEqual(dedicated.tag_keys(), ("wib-deadline",))
        self.assertFalse(dedicated.should_unstar())

    def test_preprocess_body_removes_quotes_reply_tail_and_signature_before_limit(self) -> None:
        body = (
            "今回の本文です。\n"
            "> 前回の引用1\n"
            "> 前回の引用2\n"
            "続きです。\n"
            "-- \n"
            "署名\n"
        )
        self.assertEqual(preprocess_body(body, 100), "今回の本文です。\n続きです。")
        self.assertEqual(preprocess_body("123456789", 4), "1234")


if __name__ == "__main__":
    unittest.main()
