from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.application import DeadlineService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.deadline_workflow import DeadlineWorkflowService
from workinbox.models import DeadlineCreatedBy, EmailMessage


class RecordingWorkTagService:
    def __init__(self) -> None:
        self.operations: list[tuple[str, str, bool]] = []

    def set_tag(self, message_id: str, key: str, *, enabled: bool) -> None:
        self.operations.append((message_id, key, enabled))


class DeadlineWorkflowTest(unittest.TestCase):
    def make_config(self, path: Path) -> AppConfig:
        return AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
        )

    def seed_message(self, database: EmailDatabase) -> str:
        message_id = "<mail@example>"
        database.synchronize(
            [
                EmailMessage(
                    message_id,
                    "sender@example.com",
                    "me@example.com",
                    "締切のお知らせ",
                    "2026-08-10T00:00:00+09:00",
                    "8月20日までに提出してください。",
                )
            ]
        )
        return message_id

    def make_services(self, path: Path):
        database = EmailDatabase(path)
        database.initialize()
        message_id = self.seed_message(database)
        deadline_service = DeadlineService(self.make_config(path), database=database)
        tag_service = RecordingWorkTagService()
        workflow = DeadlineWorkflowService(deadline_service, tag_service)
        return message_id, deadline_service, tag_service, workflow

    def test_pending_candidate_keeps_message_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            message_id, deadline_service, tag_service, workflow = self.make_services(
                Path(directory) / "workinbox.db"
            )
            deadline_service.add_candidate(message_id, "提出締切", due_at="2026-08-20")

            completion = workflow.complete_if_ready(message_id)

            self.assertFalse(completion.completed)
            self.assertEqual(tag_service.operations, [])

    def test_all_rejected_removes_deadline_tag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            message_id, deadline_service, tag_service, workflow = self.make_services(
                Path(directory) / "workinbox.db"
            )
            first = deadline_service.add_candidate(message_id, "候補1", due_at="2026-08-20")
            second = deadline_service.add_candidate(message_id, "候補2", due_at="2026-08-21")

            workflow.reject_candidate(first.id)
            candidate, completion = workflow.reject_candidate(second.id)

            self.assertEqual(candidate.source_message_id, message_id)
            self.assertTrue(completion.completed)
            self.assertEqual(completion.registered_count, 0)
            self.assertEqual(completion.rejected_count, 2)
            self.assertEqual(
                tag_service.operations,
                [(message_id, "wib-deadline", False)],
            )

    def test_registered_candidate_adds_deadline_done_after_all_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            message_id, deadline_service, tag_service, workflow = self.make_services(
                Path(directory) / "workinbox.db"
            )
            registered = deadline_service.add_candidate(
                message_id,
                "提出締切",
                due_at="2026-08-20",
                created_by=DeadlineCreatedBy.AI,
            )
            rejected = deadline_service.add_candidate(
                message_id,
                "参考候補",
                due_at="2026-08-21",
                created_by=DeadlineCreatedBy.AI,
            )

            deadline, first_completion = workflow.register_candidate(registered.id)
            self.assertEqual(deadline.source_message_id, message_id)
            self.assertFalse(first_completion.completed)
            self.assertEqual(tag_service.operations, [])

            _, final_completion = workflow.reject_candidate(rejected.id)

            self.assertTrue(final_completion.completed)
            self.assertEqual(final_completion.registered_count, 1)
            self.assertEqual(final_completion.rejected_count, 1)
            self.assertEqual(
                tag_service.operations,
                [(message_id, "wib-deadline-done", True)],
            )

    def test_zero_candidates_does_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            message_id, _deadline_service, tag_service, workflow = self.make_services(
                Path(directory) / "workinbox.db"
            )

            completion = workflow.complete_if_ready(message_id)

            self.assertFalse(completion.completed)
            self.assertEqual(tag_service.operations, [])


if __name__ == "__main__":
    unittest.main()
