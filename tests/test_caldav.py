from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from workinbox.application import DeadlineService
from workinbox.caldav import DeadlineCalDavService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.models import EmailMessage


class DeadlineCalDavTest(unittest.TestCase):
    def make_services(self, path: Path) -> tuple[DeadlineService, DeadlineCalDavService]:
        config = AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
        )
        database = EmailDatabase(path)
        database.initialize()
        database.synchronize([EmailMessage(
            "<source@example>", "sender@example", None, "Subject",
            "2026-09-01T00:00:00+09:00", "Body",
        )])
        service = DeadlineService(config, database=database)
        candidate = service.add_candidate("<source@example>", "Original", due_at="2026-09-10")
        service.register_candidate(candidate.id, description="Original note")
        return service, DeadlineCalDavService(service)

    def test_existing_database_is_migrated_and_web_update_preserves_caldav_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            service, caldav = self.make_services(path)
            deadline = caldav.all()[0]
            body = caldav.render(deadline).replace(
                "SUMMARY:Original", "SUMMARY:From Thunderbird"
            ).replace(
                "DUE;VALUE=DATE:20260910",
                "DTSTART;VALUE=DATE:20260903\r\nDUE;VALUE=DATE:20260912",
            ).replace(
                "PERCENT-COMPLETE:0\r\nPRIORITY:0",
                "PERCENT-COMPLETE:0\r\nPRIORITY:1",
            )
            updated = caldav.update(deadline, body)
            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertEqual(updated.start_at, "2026-09-03")
            self.assertEqual(updated.priority, 1)

            service.revise_deadline(
                updated.id, title="From WIB", due_at="2026-09-13", description="WIB note"
            )
            after_web = service.deadline(updated.id)
            assert after_web is not None
            self.assertEqual(after_web.start_at, "2026-09-03")
            self.assertEqual(after_web.priority, 1)
            self.assertGreater(after_web.version, updated.version)

    def test_completion_round_trip_and_summary_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service, caldav = self.make_services(Path(directory) / "workinbox.db")
            deadline = caldav.all()[0]
            completed_at = "20260902T010203Z"
            body = caldav.render(deadline).replace(
                "STATUS:NEEDS-ACTION", "STATUS:COMPLETED"
            ).replace(
                "PERCENT-COMPLETE:0", f"PERCENT-COMPLETE:100\r\nCOMPLETED:{completed_at}"
            )
            updated = caldav.update(deadline, body)
            assert updated is not None
            self.assertEqual(updated.status, "COMPLETED")
            self.assertEqual(updated.percent_complete, 100)
            self.assertEqual(
                service.summary(now=datetime(2026, 9, 2, tzinfo=timezone.utc))["due_within_7_days"],
                0,
            )

    def test_stale_update_and_identity_change_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, caldav = self.make_services(Path(directory) / "workinbox.db")
            deadline = caldav.all()[0]
            body = caldav.render(deadline)
            self.assertIsNotNone(caldav.update(deadline, body))
            self.assertIsNone(caldav.update(deadline, body))
            with self.assertRaisesRegex(ValueError, "UID cannot be changed"):
                caldav.update(deadline, body.replace(
                    f"UID:workinbox-deadline-{deadline.id}@workinbox.local",
                    "UID:changed@example",
                ))

    def test_migration_adds_caldav_columns_to_legacy_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE deadlines (id INTEGER PRIMARY KEY, source_message_id TEXT NOT NULL, title TEXT NOT NULL, due_at TEXT NOT NULL, timezone TEXT, description TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            EmailDatabase(path).initialize()
            with sqlite3.connect(path) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(deadlines)")}
            self.assertTrue({"start_at", "status", "completed_at", "percent_complete", "priority", "version"} <= columns)


if __name__ == "__main__":
    unittest.main()
