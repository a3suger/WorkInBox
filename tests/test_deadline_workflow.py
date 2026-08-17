from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.application import DeadlineService, WorkTagService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.deadline_workflow import DeadlineWorkflowService
from workinbox.models import DeadlineCreatedBy, EmailMessage, ImapFlagsSnapshot, TrackingStatus


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


class DeadlineWorkflowTest(unittest.TestCase):
    def make_config(self, path: Path) -> AppConfig:
        return AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
        )

    def make_services(self, path: Path, flags: tuple[str, ...] = ("\\Flagged", "wib-deadline")):
        database = EmailDatabase(path)
        database.initialize()
        message_id = "<mail@example>"
        database.synchronize([
            EmailMessage(
                message_id,
                "sender@example.com",
                "me@example.com",
                "締切のお知らせ",
                "2026-08-10T00:00:00+09:00",
                "8月20日までに提出してください。",
                mailbox="INBOX",
                uidvalidity=10,
                uid=1,
            )
        ])
        config = self.make_config(path)
        imap = FakeImapClient(flags)
        deadline_service = DeadlineService(config, database=database)
        tag_service = WorkTagService(config, database=database, imap_client=imap)
        workflow = DeadlineWorkflowService(deadline_service, tag_service)
        return message_id, database, imap, deadline_service, workflow

    def test_pending_candidate_keeps_message_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            message_id, _database, imap, deadline_service, workflow = self.make_services(
                Path(directory) / "workinbox.db"
            )
            deadline_service.add_candidate(message_id, "提出締切", due_at="2026-08-20")

            completion = workflow.complete_if_ready(message_id)

            self.assertFalse(completion.completed)
            self.assertEqual(imap.flags, ("\\Flagged", "wib-deadline"))

    def test_all_rejected_without_other_work_adds_bulk_and_unstars(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            message_id, database, imap, deadline_service, workflow = self.make_services(
                Path(directory) / "workinbox.db"
            )
            first = deadline_service.add_candidate(message_id, "候補1", due_at="2026-08-20")
            second = deadline_service.add_candidate(message_id, "候補2", due_at="2026-08-21")

            workflow.reject_candidate(first.id)
            _candidate, completion = workflow.reject_candidate(second.id)

            self.assertTrue(completion.completed)
            self.assertNotIn("wib-deadline", imap.flags)
            self.assertIn("wib-bulk", imap.flags)
            self.assertNotIn("\\Flagged", imap.flags)
            self.assertEqual(
                database.list_tracked_emails(active=False)[0].tracking_status,
                TrackingStatus.INACTIVE_UNSTARRED,
            )

    def test_registered_candidate_with_normal_workflow_keeps_star(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            message_id, database, imap, deadline_service, workflow = self.make_services(
                Path(directory) / "workinbox.db",
                ("\\Flagged", "wib-deadline", "wib-review"),
            )
            candidate = deadline_service.add_candidate(
                message_id,
                "提出締切",
                due_at="2026-08-20",
                created_by=DeadlineCreatedBy.AI,
            )

            deadline, completion = workflow.register_candidate(candidate.id)

            self.assertEqual(deadline.source_message_id, message_id)
            self.assertTrue(completion.completed)
            self.assertIn("wib-deadline-done", imap.flags)
            self.assertIn("wib-review", imap.flags)
            self.assertIn("\\Flagged", imap.flags)
            self.assertNotIn("wib-bulk", imap.flags)
            self.assertEqual(len(database.list_tracked_emails(active=True)), 1)

    def test_deadline_end_keeps_star_while_schedule_workflow_unfinished(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            message_id, _database, imap, deadline_service, workflow = self.make_services(
                Path(directory) / "workinbox.db",
                ("\\Flagged", "wib-deadline", "wib-schedule"),
            )
            candidate = deadline_service.add_candidate(message_id, "提出締切", due_at="2026-08-20")

            _deadline, completion = workflow.register_candidate(candidate.id)

            self.assertTrue(completion.completed)
            self.assertIn("wib-deadline-done", imap.flags)
            self.assertIn("wib-schedule", imap.flags)
            self.assertNotIn("wib-schedule-done", imap.flags)
            self.assertIn("\\Flagged", imap.flags)
            self.assertNotIn("wib-bulk", imap.flags)

    def test_zero_candidates_does_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            message_id, _database, imap, _deadline_service, workflow = self.make_services(
                Path(directory) / "workinbox.db"
            )

            completion = workflow.complete_if_ready(message_id)

            self.assertFalse(completion.completed)
            self.assertEqual(imap.flags, ("\\Flagged", "wib-deadline"))


if __name__ == "__main__":
    unittest.main()
