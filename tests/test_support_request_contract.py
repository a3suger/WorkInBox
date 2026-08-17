from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SupportRequestContractTest(unittest.TestCase):
    def test_support_request_is_new_thread_with_origin_header(self) -> None:
        background = (
            ROOT / "thunderbird" / "workinbox-extension" / "background.js"
        ).read_text(encoding="utf-8")

        self.assertIn('const WORKINBOX_ORIGIN_HEADER = "X-WorkInBox-Origin-Message-ID";', background)
        self.assertIn("messenger.compose.beginNew()", background)
        self.assertIn("customHeaders: withOriginHeader", background)
        self.assertNotIn("messenger.compose.beginReply(originMessage.id", background)
        self.assertNotIn("messenger.compose.beginForward(originMessage.id", background)

    def test_web_bridge_no_longer_sends_reply_or_forward_mode(self) -> None:
        bridge = (
            ROOT / "thunderbird" / "workinbox-extension" / "workinbox_bridge.js"
        ).read_text(encoding="utf-8")
        template = (
            ROOT / "src" / "workinbox" / "templates" / "schedules.html"
        ).read_text(encoding="utf-8")

        self.assertNotIn('data.get("method")', bridge)
        self.assertNotIn('data.get("keep_reply_subject")', bridge)
        self.assertNotIn('name="method"', template)
        self.assertNotIn('name="keep_reply_subject"', template)
        self.assertIn("別スレッドの新規メール", template)


if __name__ == "__main__":
    unittest.main()
