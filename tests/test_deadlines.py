from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.application import DeadlineService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.models import (
    DeadlineCandidateStatus,
    DeadlineCreatedBy,
    EmailMessage,
)


class DeadlineSupportTest(unittest.TestCase):
    def make_config(self, path: Path) -> AppConfig:
        return AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
        )

    def seed_message(self, database: EmailDatabase, message_id: str = "<mail@example>") -> None:
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

    def test_initialize_creates_deadline_tables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()

            import sqlite3

            with sqlite3.connect(path) as connection:
                names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            self.assertIn("deadline_candidates", names)
            self.assertIn("deadlines", names)

    def test_candidate_can_be_revised_and_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed_message(database)
            service = DeadlineService(self.make_config(path), database=database)

            candidate = service.add_candidate(
                "<mail@example>",
                "提出締切",
                due_at=None,
                source_text="別紙参照",
                created_by=DeadlineCreatedBy.AI,
                needs_review=True,
            )
            self.assertEqual(candidate.status, DeadlineCandidateStatus.PENDING)
            self.assertTrue(candidate.needs_review)

            candidate = service.revise_candidate(
                candidate.id,
                title="最終提出締切",
                due_at="2026-08-20",
                source_text="8月20日まで",
                needs_review=False,
            )
            self.assertEqual(candidate.title, "最終提出締切")
            self.assertEqual(candidate.due_at, "2026-08-20")
            self.assertFalse(candidate.needs_review)

            candidate = service.reject_candidate(candidate.id)
            self.assertEqual(candidate.status, DeadlineCandidateStatus.REJECTED)
            with self.assertRaises(ValueError):
                service.reject_candidate(candidate.id)

    def test_register_candidate_creates_formal_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed_message(database)
            service = DeadlineService(self.make_config(path), database=database)

            candidate = service.add_candidate(
                "<mail@example>",
                "提出締切",
                due_at="2026-08-20T17:00:00+09:00",
                created_by=DeadlineCreatedBy.AI,
            )
            deadline = service.register_candidate(
                candidate.id,
                timezone_name="Asia/Tokyo",
                description="メールから登録",
            )

            self.assertEqual(deadline.source_message_id, "<mail@example>")
            self.assertEqual(deadline.title, "提出締切")
            self.assertEqual(deadline.due_at, "2026-08-20T17:00:00+09:00")
            self.assertEqual(deadline.timezone, "Asia/Tokyo")
            self.assertEqual(deadline.created_by, DeadlineCreatedBy.AI)
            self.assertEqual(
                service.candidates("<mail@example>")[0].status,
                DeadlineCandidateStatus.REGISTERED,
            )
            self.assertEqual(service.deadlines("<mail@example>"), [deadline])

    def test_candidate_without_due_at_cannot_be_registered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed_message(database)
            service = DeadlineService(self.make_config(path), database=database)

            candidate = service.add_candidate("<mail@example>", "日付未定の締切")
            with self.assertRaises(ValueError):
                service.register_candidate(candidate.id)
            self.assertEqual(
                service.candidates("<mail@example>")[0].status,
                DeadlineCandidateStatus.PENDING,
            )

    def test_service_rejects_unknown_message_and_empty_title(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            service = DeadlineService(self.make_config(path), database=database)

            with self.assertRaises(ValueError):
                service.add_candidate("<missing@example>", "締切")

            self.seed_message(database)
            with self.assertRaises(ValueError):
                service.add_candidate("<mail@example>", "   ")


if __name__ == "__main__":
    unittest.main()
