from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.models import EmailMessage, ImapFlagsSnapshot, TrackingStatus
from workinbox.normal_workflow import NormalWorkflowCompletionService
from workinbox.record_store import RecordStore


class FakeImapClient:
    def __init__(self, flags: tuple[str, ...]) -> None:
        self.flags = flags

    def inspect_flags(self, uid: int, *, expected_uidvalidity: int | None = None):
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, self.flags)

    def set_keyword(
        self,
        uid: int,
        keyword: str,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ):
        flags = list(self.flags)
        if enabled and keyword not in flags:
            flags.append(keyword)
        if not enabled:
            flags = [flag for flag in flags if flag != keyword]
        self.flags = tuple(flags)
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, self.flags)

    def set_flagged(
        self,
        uid: int,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ):
        flags = [flag for flag in self.flags if flag != "\\Flagged"]
        if enabled:
            flags.append("\\Flagged")
        self.flags = tuple(flags)
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, self.flags)


class NormalWorkflowCompletionTest(unittest.TestCase):
    def setUpTarget(self, path: Path, flags: tuple[str, ...]):
        database = EmailDatabase(path)
        database.initialize()
        database.synchronize([
            EmailMessage(
                "<mail@example>",
                "sender@example.com",
                "me@example.com",
                "確認事項",
                None,
                "本文",
                mailbox="INBOX",
                uidvalidity=10,
                uid=7,
            )
        ])
        config = AppConfig(
            ImapConfig("imap.example", 993, "user@example.com", "pass", "INBOX", 7),
            DatabaseConfig(path),
        )
        imap = FakeImapClient(flags)
        records = RecordStore(path)
        service = NormalWorkflowCompletionService(
            config,
            database=database,
            imap_client=imap,
            record_store=records,
        )
        return database, imap, records, service

    def test_normal_end_preserves_workflow_adds_bulk_and_unstars(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database, imap, records, service = self.setUpTarget(
                path, ("\\Flagged", "wib-review")
            )

            result = service.complete("<mail@example>")

            self.assertIsNone(result.saved_record)
            self.assertIn("wib-review", imap.flags)
            self.assertIn("wib-bulk", imap.flags)
            self.assertNotIn("\\Flagged", imap.flags)
            self.assertEqual(records.list(), [])
            self.assertEqual(
                database.list_tracked_emails(active=False)[0].tracking_status,
                TrackingStatus.INACTIVE_UNSTARRED,
            )

    def test_record_end_preserves_workflow_removes_bulk_and_unstars(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database, imap, records, service = self.setUpTarget(
                path, ("\\Flagged", "wib-watch", "wib-bulk")
            )

            result = service.save_record_and_complete(
                "<mail@example>",
                summary="後で参照する要点",
                note="担当者に共有",
            )

            self.assertIsNotNone(result.saved_record)
            self.assertIn("wib-watch", imap.flags)
            self.assertNotIn("wib-bulk", imap.flags)
            self.assertNotIn("\\Flagged", imap.flags)
            saved = records.list()[0]
            self.assertEqual(saved.source_message_id, "<mail@example>")
            self.assertEqual(saved.source_account, "user@example.com")
            self.assertEqual(saved.title, "確認事項")
            self.assertEqual(saved.summary, "後で参照する要点")
            self.assertEqual(saved.note, "担当者に共有")
            self.assertEqual(
                database.list_tracked_emails(active=False)[0].tracking_status,
                TrackingStatus.INACTIVE_UNSTARRED,
            )

    def test_non_normal_workflow_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            _database, imap, records, service = self.setUpTarget(
                path, ("\\Flagged", "wib-schedule")
            )

            with self.assertRaisesRegex(ValueError, "not in a normal workflow"):
                service.complete("<mail@example>")

            self.assertIn("\\Flagged", imap.flags)
            self.assertEqual(records.list(), [])


if __name__ == "__main__":
    unittest.main()
