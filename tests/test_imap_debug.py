from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.imap_debug import inspect_flags
from workinbox.models import ImapFlagsSnapshot


class FakeImapClient:
    def __init__(self, config: ImapConfig) -> None:
        self.config = config

    def inspect_flags(self, uid: int) -> ImapFlagsSnapshot:
        return ImapFlagsSnapshot(
            mailbox=self.config.mailbox,
            uidvalidity=55,
            uid=uid,
            flags=("\\Seen", "\\Flagged", "$label1"),
        )


class ImapDebugTest(unittest.TestCase):
    def test_inspect_flags_prints_snapshot(self) -> None:
        config = AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(Path("workinbox.db")),
        )
        output = io.StringIO()

        with (
            patch("workinbox.imap_debug.load_config", return_value=config),
            patch("workinbox.imap_debug.ImapClient", FakeImapClient),
            redirect_stdout(output),
        ):
            result = inspect_flags("ignored.yaml", 12345)

        self.assertEqual(result, 0)
        self.assertEqual(
            output.getvalue(),
            "Mailbox: INBOX\n"
            "UIDVALIDITY: 55\n"
            "UID: 12345\n"
            "FLAGS:\n"
            "  \\Seen\n"
            "  \\Flagged\n"
            "  $label1\n",
        )


if __name__ == "__main__":
    unittest.main()
