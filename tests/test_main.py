from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.main import synchronize
from workinbox.models import (
    EmailMessage,
    ImapCheckResult,
    ImapCheckState,
    TrackingStatus,
)


class FakeImapClient:
    def __init__(self, config: ImapConfig) -> None:
        self.config = config

    def synchronize(self, existing):
        ids = {reference.message_id for reference in existing}
        assert ids == {
            "<unstarred@example>",
            "<moved@example>",
            "<error@example>",
            "<active@example>",
        }
        return (
            [
                ImapCheckResult("<unstarred@example>", ImapCheckState.UNSTARRED),
                ImapCheckResult("<moved@example>", ImapCheckState.MISSING),
                ImapCheckResult("<error@example>", ImapCheckState.ERROR, "temporary"),
                ImapCheckResult("<active@example>", ImapCheckState.FLAGGED),
            ],
            [
                EmailMessage(
                    "<active@example>", "a@example", None, None, None, None,
                    mailbox="INBOX", uidvalidity=10, uid=4,
                ),
                EmailMessage(
                    "<reactivate@example>", "r@example", None, None, None, None,
                    mailbox="INBOX", uidvalidity=10, uid=5,
                ),
                EmailMessage(
                    "<new@example>", "n@example", None, None, None, None,
                    mailbox="INBOX", uidvalidity=10, uid=6,
                ),
            ],
        )


class MainSynchronizeTest(unittest.TestCase):
    def test_v02_tracking_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            for index, message_id in enumerate(
                [
                    "<unstarred@example>",
                    "<moved@example>",
                    "<error@example>",
                    "<active@example>",
                    "<reactivate@example>",
                ],
                start=1,
            ):
                database.synchronize([
                    EmailMessage(
                        message_id, "x@example", None, None, None, None,
                        mailbox="INBOX", uidvalidity=10, uid=index,
                    )
                ])
            database.update_tracking_status(
                "<reactivate@example>", TrackingStatus.INACTIVE_UNSTARRED
            )

            config = AppConfig(
                ImapConfig("imap.example", 993, "user", "pass", "INBOX"),
                DatabaseConfig(path),
            )
            with (
                patch("workinbox.main.load_config", return_value=config),
                patch("workinbox.main.ImapClient", FakeImapClient),
            ):
                self.assertEqual(synchronize("ignored.yaml"), (3, 1, 2))

            with sqlite3.connect(path) as connection:
                rows = dict(
                    connection.execute(
                        "SELECT message_id, tracking_status FROM emails"
                    ).fetchall()
                )
            self.assertEqual(rows["<unstarred@example>"], "inactive_unstarred")
            self.assertEqual(rows["<moved@example>"], "inactive_moved")
            self.assertEqual(rows["<error@example>"], "active")
            self.assertEqual(rows["<active@example>"], "active")
            self.assertEqual(rows["<reactivate@example>"], "active")
            self.assertEqual(rows["<new@example>"], "active")


if __name__ == "__main__":
    unittest.main()
