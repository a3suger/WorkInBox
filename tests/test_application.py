from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from workinbox.application import SyncMode, SynchronizationService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.models import (
    EmailMessage,
    ImapCheckResult,
    ImapCheckState,
    ImapReference,
    TrackingStatus,
)


class FakeImapClient:
    def __init__(
        self,
        checks: list[ImapCheckResult],
        messages: list[EmailMessage] | None = None,
    ) -> None:
        self.checks = checks
        self.messages = messages or []
        self.received_references: list[ImapReference] = []

    def synchronize(
        self,
        existing: list[ImapReference],
    ) -> tuple[list[ImapCheckResult], list[EmailMessage]]:
        self.received_references = list(existing)
        return self.checks, self.messages


class SynchronizationServiceTest(unittest.TestCase):
    def make_config(self, path: Path) -> AppConfig:
        return AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
        )

    def seed(
        self,
        database: EmailDatabase,
        message_id: str,
        uid: int,
        status: TrackingStatus = TrackingStatus.ACTIVE,
    ) -> None:
        database.synchronize(
            [
                EmailMessage(
                    message_id,
                    "sender@example.com",
                    None,
                    None,
                    None,
                    None,
                    mailbox="INBOX",
                    uidvalidity=10,
                    uid=uid,
                )
            ]
        )
        if status != TrackingStatus.ACTIVE:
            database.update_tracking_status(message_id, status)

    def test_normal_sync_checks_only_active_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed(database, "<active@example>", 1)
            self.seed(
                database,
                "<inactive@example>",
                2,
                TrackingStatus.INACTIVE_UNSTARRED,
            )

            imap = FakeImapClient(
                [ImapCheckResult("<active@example>", ImapCheckState.MISSING)],
                [
                    EmailMessage(
                        "<new@example>",
                        "new@example.com",
                        None,
                        None,
                        None,
                        None,
                        mailbox="INBOX",
                        uidvalidity=10,
                        uid=3,
                    )
                ],
            )
            service = SynchronizationService(
                self.make_config(path),
                database=database,
                imap_client=imap,
            )

            result = service.normal_sync()

            self.assertEqual(
                [reference.message_id for reference in imap.received_references],
                ["<active@example>"],
            )
            self.assertEqual(result.mode, SyncMode.NORMAL)
            self.assertEqual(result.checked, 1)
            self.assertEqual(result.flagged, 1)
            self.assertEqual(result.added, 1)
            self.assertEqual(result.reactivated, 0)
            self.assertEqual(result.inactivated, 1)

            with sqlite3.connect(path) as connection:
                rows = dict(
                    connection.execute(
                        "SELECT message_id, tracking_status FROM emails"
                    ).fetchall()
                )
            self.assertEqual(rows["<active@example>"], "inactive_moved")
            self.assertEqual(rows["<inactive@example>"], "inactive_unstarred")
            self.assertEqual(rows["<new@example>"], "active")

    def test_full_recheck_includes_inactive_and_can_reactivate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed(database, "<active@example>", 1)
            self.seed(
                database,
                "<unstarred@example>",
                2,
                TrackingStatus.INACTIVE_UNSTARRED,
            )
            self.seed(
                database,
                "<moved@example>",
                3,
                TrackingStatus.INACTIVE_MOVED,
            )

            imap = FakeImapClient(
                [
                    ImapCheckResult("<active@example>", ImapCheckState.FLAGGED),
                    ImapCheckResult("<unstarred@example>", ImapCheckState.FLAGGED),
                    ImapCheckResult("<moved@example>", ImapCheckState.MISSING),
                ]
            )
            service = SynchronizationService(
                self.make_config(path),
                database=database,
                imap_client=imap,
            )

            result = service.full_recheck()

            self.assertEqual(
                [reference.message_id for reference in imap.received_references],
                [
                    "<active@example>",
                    "<unstarred@example>",
                    "<moved@example>",
                ],
            )
            self.assertEqual(result.mode, SyncMode.FULL_RECHECK)
            self.assertEqual(result.checked, 3)
            self.assertEqual(result.reactivated, 1)
            self.assertEqual(result.inactivated, 0)

            with sqlite3.connect(path) as connection:
                rows = dict(
                    connection.execute(
                        "SELECT message_id, tracking_status FROM emails"
                    ).fetchall()
                )
            self.assertEqual(rows["<active@example>"], "active")
            self.assertEqual(rows["<unstarred@example>"], "active")
            self.assertEqual(rows["<moved@example>"], "inactive_moved")

    def test_per_message_error_is_reported_without_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed(database, "<error@example>", 1)

            imap = FakeImapClient(
                [
                    ImapCheckResult(
                        "<error@example>",
                        ImapCheckState.ERROR,
                        "temporary failure",
                    )
                ]
            )
            service = SynchronizationService(
                self.make_config(path),
                database=database,
                imap_client=imap,
            )

            result = service.normal_sync()

            self.assertEqual(len(result.errors), 1)
            self.assertEqual(result.errors[0].message_id, "<error@example>")
            self.assertEqual(result.errors[0].message, "temporary failure")
            with sqlite3.connect(path) as connection:
                status = connection.execute(
                    "SELECT tracking_status FROM emails WHERE message_id = ?",
                    ("<error@example>",),
                ).fetchone()[0]
            self.assertEqual(status, "active")


if __name__ == "__main__":
    unittest.main()
