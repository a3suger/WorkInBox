from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from workinbox.ai_classifier import AiClassification
from workinbox.application import SyncMode, SynchronizationService, WorkTagService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.models import (
    EmailMessage,
    ImapCheckResult,
    ImapCheckState,
    ImapFlagsSnapshot,
    ImapReference,
    TrackingStatus,
)


class FakeClassifier:
    def __init__(self, result: AiClassification | None = None) -> None:
        self.result = result or AiClassification(False, False, False, True, False, "review")
        self.messages: list[EmailMessage] = []

    def classify(self, message: EmailMessage) -> AiClassification:
        self.messages.append(message)
        return self.result


class FakeImapClient:
    def __init__(
        self,
        checks: list[ImapCheckResult],
        messages: list[EmailMessage] | None = None,
        *,
        flags_by_uid: dict[int, tuple[str, ...]] | None = None,
    ) -> None:
        self.checks = checks
        self.messages = messages or []
        self.received_references: list[ImapReference] = []
        self.flags_by_uid = flags_by_uid or {}
        self.keyword_updates: list[tuple[int, tuple[str, ...], bool, int | None]] = []

    def synchronize(
        self,
        existing: list[ImapReference],
    ) -> tuple[list[ImapCheckResult], list[EmailMessage]]:
        self.received_references = list(existing)
        return self.checks, self.messages

    def inspect_flags(
        self,
        uid: int,
        *,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        flags = self.flags_by_uid.get(uid, ("wib-review",))
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, flags)

    def set_keywords(
        self,
        uid: int,
        keywords: tuple[str, ...],
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        keys = tuple(keywords)
        self.keyword_updates.append((uid, keys, enabled, expected_uidvalidity))
        current = list(self.flags_by_uid.get(uid, ()))
        if enabled:
            for keyword in keys:
                if keyword not in current:
                    current.append(keyword)
        else:
            current = [flag for flag in current if flag not in keys]
        self.flags_by_uid[uid] = tuple(current)
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, tuple(current))


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
            self.seed(database, "<inactive@example>", 2, TrackingStatus.INACTIVE_UNSTARRED)

            imap = FakeImapClient(
                [ImapCheckResult("<active@example>", ImapCheckState.MISSING)],
                [
                    EmailMessage(
                        "<new@example>", "new@example.com", None, None, None, None,
                        mailbox="INBOX", uidvalidity=10, uid=3,
                    )
                ],
            )
            service = SynchronizationService(
                self.make_config(path), database=database, imap_client=imap,
                classifier=FakeClassifier(),
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
            self.assertEqual(result.ai_classified, 0)

            with sqlite3.connect(path) as connection:
                rows = dict(connection.execute("SELECT message_id, tracking_status FROM emails").fetchall())
            self.assertEqual(rows["<active@example>"], "inactive_moved")
            self.assertEqual(rows["<inactive@example>"], "inactive_unstarred")
            self.assertEqual(rows["<new@example>"], "active")

    def test_normal_sync_classifies_unclassified_active_mail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            message = EmailMessage(
                "<new@example>",
                "sender@example.com",
                "me@example.com",
                "提出してください",
                None,
                "8月20日までに提出してください。",
                mailbox="INBOX",
                uidvalidity=10,
                uid=3,
            )
            imap = FakeImapClient([], [message], flags_by_uid={3: ("\\Flagged",)})
            classifier = FakeClassifier(
                AiClassification(True, True, False, False, False, "期限付きの日程調整")
            )
            service = SynchronizationService(
                self.make_config(path), database=database, imap_client=imap,
                classifier=classifier,
            )

            result = service.normal_sync()

            self.assertEqual(result.ai_classified, 1)
            self.assertEqual(result.ai_errors, ())
            self.assertEqual([item.message_id for item in classifier.messages], ["<new@example>"])
            self.assertEqual(
                imap.keyword_updates,
                [(3, ("wib-deadline", "wib-schedule"), True, 10)],
            )

    def test_pending_view_and_resolution_use_normal_workflow_tags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            database.synchronize(
                [
                    EmailMessage(
                        "<pending@example>",
                        "sender@example.com",
                        "me@example.com",
                        "要確認",
                        None,
                        "添付を確認して回答してください。",
                        mailbox="INBOX",
                        uidvalidity=10,
                        uid=4,
                    ),
                    EmailMessage(
                        "<review@example>",
                        "sender@example.com",
                        "me@example.com",
                        "通常",
                        None,
                        "確認だけです。",
                        mailbox="INBOX",
                        uidvalidity=10,
                        uid=5,
                    ),
                ]
            )
            imap = FakeImapClient(
                [],
                flags_by_uid={
                    4: ("\\Flagged", "wib-pending"),
                    5: ("\\Flagged", "wib-review"),
                },
            )
            service = WorkTagService(
                self.make_config(path), database=database, imap_client=imap,
            )

            pending = service.pending_emails()

            self.assertEqual([item.email.message_id for item in pending], ["<pending@example>"])
            self.assertEqual(pending[0].body, "添付を確認して回答してください。")

            service.resolve_pending("<pending@example>", "answer")

            self.assertIn("wib-answer", imap.flags_by_uid[4])
            self.assertNotIn("wib-pending", imap.flags_by_uid[4])
            self.assertEqual(
                imap.keyword_updates,
                [
                    (4, ("wib-answer",), True, 10),
                    (4, ("wib-pending",), False, 10),
                ],
            )

    def test_full_recheck_includes_inactive_and_can_reactivate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed(database, "<active@example>", 1)
            self.seed(database, "<unstarred@example>", 2, TrackingStatus.INACTIVE_UNSTARRED)
            self.seed(database, "<moved@example>", 3, TrackingStatus.INACTIVE_MOVED)

            imap = FakeImapClient(
                [
                    ImapCheckResult("<active@example>", ImapCheckState.FLAGGED),
                    ImapCheckResult("<unstarred@example>", ImapCheckState.FLAGGED),
                    ImapCheckResult("<moved@example>", ImapCheckState.MISSING),
                ]
            )
            service = SynchronizationService(
                self.make_config(path), database=database, imap_client=imap,
                classifier=FakeClassifier(),
            )
            result = service.full_recheck()

            self.assertEqual(
                [reference.message_id for reference in imap.received_references],
                ["<active@example>", "<unstarred@example>", "<moved@example>"],
            )
            self.assertEqual(result.mode, SyncMode.FULL_RECHECK)
            self.assertEqual(result.checked, 3)
            self.assertEqual(result.reactivated, 1)
            self.assertEqual(result.inactivated, 0)
            self.assertEqual(result.ai_classified, 0)

            with sqlite3.connect(path) as connection:
                rows = dict(connection.execute("SELECT message_id, tracking_status FROM emails").fetchall())
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
                [ImapCheckResult("<error@example>", ImapCheckState.ERROR, "temporary failure")]
            )
            service = SynchronizationService(
                self.make_config(path), database=database, imap_client=imap,
                classifier=FakeClassifier(),
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
