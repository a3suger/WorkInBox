from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.imap_tag_debug import TEST_KEYWORD, set_deadline_tag
from workinbox.models import ImapFlagsSnapshot


class FakeImapClient:
    calls: list[tuple[int, str, bool]] = []

    def __init__(self, config: ImapConfig) -> None:
        self.config = config

    def set_keyword(self, uid: int, keyword: str, *, enabled: bool) -> ImapFlagsSnapshot:
        FakeImapClient.calls.append((uid, keyword, enabled))
        flags = ("\\Seen", "$label1", keyword) if enabled else ("\\Seen", "$label1")
        return ImapFlagsSnapshot(
            mailbox=self.config.mailbox,
            uidvalidity=55,
            uid=uid,
            flags=flags,
        )


class ImapTagDebugTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeImapClient.calls = []
        self.config = AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(Path("workinbox.db")),
        )

    def test_add_deadline_tag_uses_fixed_workinbox_keyword(self) -> None:
        output = io.StringIO()
        with (
            patch("workinbox.imap_tag_debug.load_config", return_value=self.config),
            patch("workinbox.imap_tag_debug.ImapClient", FakeImapClient),
            redirect_stdout(output),
        ):
            result = set_deadline_tag("ignored.yaml", 12345, enabled=True)

        self.assertEqual(result, 0)
        self.assertEqual(FakeImapClient.calls, [(12345, TEST_KEYWORD, True)])
        self.assertIn("wib-deadline: added\n", output.getvalue())
        self.assertIn("  wib-deadline\n", output.getvalue())

    def test_remove_deadline_tag_uses_fixed_workinbox_keyword(self) -> None:
        output = io.StringIO()
        with (
            patch("workinbox.imap_tag_debug.load_config", return_value=self.config),
            patch("workinbox.imap_tag_debug.ImapClient", FakeImapClient),
            redirect_stdout(output),
        ):
            result = set_deadline_tag("ignored.yaml", 12345, enabled=False)

        self.assertEqual(result, 0)
        self.assertEqual(FakeImapClient.calls, [(12345, TEST_KEYWORD, False)])
        self.assertIn("wib-deadline: removed\n", output.getvalue())
        self.assertNotIn("  wib-deadline\n", output.getvalue())


if __name__ == "__main__":
    unittest.main()
