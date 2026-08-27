from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from workinbox.application import DeadlineService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.deadline_ics import DeadlineIcsService
from workinbox.models import DeadlineCreatedBy, EmailMessage


class DeadlineIcsTest(unittest.TestCase):
    def make_config(self, path: Path) -> AppConfig:
        return AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
        )

    def seed_message(self, database: EmailDatabase, message_id: str) -> None:
        database.synchronize(
            [
                EmailMessage(
                    message_id,
                    "sender@example.com",
                    "me@example.com",
                    "Deadline mail",
                    "2026-08-10T00:00:00+09:00",
                    "Body",
                )
            ]
        )

    def test_renders_date_only_and_timed_vtodos(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed_message(database, "<date@example>")
            self.seed_message(database, "<time@example>")
            service = DeadlineService(self.make_config(path), database=database)

            date_candidate = service.add_candidate(
                "<date@example>",
                "提出,締切",
                due_at="2026-08-20",
                created_by=DeadlineCreatedBy.AI,
            )
            date_deadline = service.register_candidate(date_candidate.id)

            time_candidate = service.add_candidate(
                "<time@example>",
                "回答締切",
                due_at="2026-08-21T17:30:00+09:00",
                created_by=DeadlineCreatedBy.USER,
            )
            time_deadline = service.register_candidate(
                time_candidate.id,
                timezone_name="Asia/Tokyo",
                description="確認;して返信",
            )

            content = DeadlineIcsService(service).render(
                source_base_url="http://localhost:8000/",
            )

            self.assertIn("BEGIN:VCALENDAR\r\n", content)
            self.assertIn("BEGIN:VTODO\r\n", content)
            self.assertIn(
                f"UID:workinbox-deadline-{date_deadline.id}@workinbox.local",
                content,
            )
            self.assertIn("SUMMARY:提出\\,締切", content)
            self.assertIn("DUE;VALUE=DATE:20260820", content)
            self.assertIn(
                f"UID:workinbox-deadline-{time_deadline.id}@workinbox.local",
                content,
            )
            self.assertIn("DUE:20260821T083000Z", content)
            self.assertIn("DESCRIPTION:確認\\;して返信", content)
            self.assertIn("X-WORKINBOX-CREATED-BY:user", content)
            self.assertIn(
                "URL:mid:date@example",
                content,
            )
            self.assertIn(
                "URL:mid:time@example",
                content,
            )
            self.assertIn(
                f"締切の確認・修正: http://localhost:8000/deadlines/{date_deadline.id}",
                content,
            )
            self.assertIn(
                "DESCRIPTION:確認\\;して返信\\n締切の確認・修正: "
                f"http://localhost:8000/deadlines/{time_deadline.id}",
                content,
            )
            self.assertTrue(content.endswith("END:VCALENDAR\r\n"))

    def test_naive_datetime_uses_stored_timezone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed_message(database, "<naive@example>")
            service = DeadlineService(self.make_config(path), database=database)

            candidate = service.add_candidate(
                "<naive@example>",
                "現地時刻締切",
                due_at="2026-08-22T09:00:00",
            )
            service.register_candidate(candidate.id, timezone_name="Asia/Tokyo")

            content = DeadlineIcsService(service).render()
            self.assertIn("DUE:20260822T000000Z", content)

    def test_revised_deadline_is_reflected_in_vtodo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed_message(database, "<revised@example>")
            service = DeadlineService(self.make_config(path), database=database)

            candidate = service.add_candidate(
                "<revised@example>",
                "元の締切",
                due_at="2026-08-22",
            )
            deadline = service.register_candidate(candidate.id)
            service.revise_deadline(
                deadline.id,
                title="更新後の締切",
                due_at="2026-08-31",
                description="更新後のメモ",
            )

            content = DeadlineIcsService(service).render(
                source_base_url="http://localhost:8000/",
            )

            self.assertIn("SUMMARY:更新後の締切", content)
            self.assertIn("DUE;VALUE=DATE:20260831", content)
            self.assertIn("DESCRIPTION:更新後のメモ\\n締切の確認・修正: ", content)
            self.assertNotIn("SUMMARY:元の締切", content)

    def test_legacy_registered_weekday_value_is_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed_message(database, "<legacy@example>")
            service = DeadlineService(self.make_config(path), database=database)

            candidate = service.add_candidate(
                "<legacy@example>",
                "旧データ締切",
                due_at="2026-09-29",
            )
            deadline = service.register_candidate(candidate.id)
            with sqlite3.connect(path) as connection:
                connection.execute(
                    "UPDATE deadlines SET due_at = ? WHERE id = ?",
                    ("2026-09-29 火曜日", deadline.id),
                )

            content = DeadlineIcsService(service).render()
            self.assertIn("SUMMARY:旧データ締切", content)
            self.assertIn("DUE;VALUE=DATE:20260929", content)


if __name__ == "__main__":
    unittest.main()
