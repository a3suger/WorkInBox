from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from workinbox.database import EmailDatabase
from workinbox.models import EmailMessage, TrackingStatus


class EmailDatabaseTest(unittest.TestCase):
    def test_synchronize_keeps_missing_messages_and_adds_new_ones(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()

            first = EmailMessage("<1@example>", "a@example", None, "One", None, "A")
            second = EmailMessage("<2@example>", "b@example", None, "Two", None, "B")

            self.assertEqual(database.synchronize([first, second]), (2, 0))
            self.assertEqual(database.synchronize([second]), (0, 0))

            with sqlite3.connect(path) as connection:
                rows = connection.execute(
                    "SELECT message_id FROM emails ORDER BY message_id"
                ).fetchall()
            self.assertEqual(rows, [("<1@example>",), ("<2@example>",)])

    def test_duplicate_message_id_is_not_added_twice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = EmailDatabase(Path(directory) / "workinbox.db")
            database.initialize()
            message = EmailMessage("<1@example>", "a@example", None, None, None, None)
            self.assertEqual(database.synchronize([message]), (1, 0))
            self.assertEqual(database.synchronize([message]), (0, 0))

    def test_inactive_message_is_reactivated_by_flagged_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            message = EmailMessage(
                "<1@example>", "a@example", None, None, None, None,
                mailbox="INBOX", uidvalidity=10, uid=20,
            )
            database.synchronize([message])
            database.update_tracking_status(
                message.message_id,
                TrackingStatus.INACTIVE_UNSTARRED,
                checked_at="2026-08-08T00:00:00+00:00",
            )

            moved_identity = EmailMessage(
                "<1@example>", "a@example", None, None, None, None,
                mailbox="INBOX", uidvalidity=10, uid=30,
            )
            self.assertEqual(database.synchronize([moved_identity]), (0, 1))

            with sqlite3.connect(path) as connection:
                row = connection.execute(
                    "SELECT tracking_status, mailbox, uidvalidity, uid FROM emails"
                ).fetchone()
            self.assertEqual(row, ("active", "INBOX", 10, 30))

    def test_active_imap_references_only_include_identified_active_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            active = EmailMessage(
                "<1@example>", "a@example", None, None, None, None,
                mailbox="INBOX", uidvalidity=10, uid=20,
            )
            no_identity = EmailMessage("<2@example>", "b@example", None, None, None, None)
            database.synchronize([active, no_identity])
            database.update_tracking_status(
                no_identity.message_id,
                TrackingStatus.INACTIVE_MOVED,
            )

            refs = database.active_imap_references("INBOX")
            self.assertEqual(len(refs), 1)
            self.assertEqual(refs[0].message_id, active.message_id)
            self.assertEqual(refs[0].uid, 20)

    def test_initialize_migrates_v01_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            with sqlite3.connect(path) as connection:
                connection.execute(
                    """
                    CREATE TABLE emails (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id TEXT NOT NULL UNIQUE,
                        sender TEXT NOT NULL,
                        recipients TEXT,
                        subject TEXT,
                        received_at TEXT,
                        body TEXT,
                        synchronized_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO emails (
                        message_id, sender, synchronized_at
                    ) VALUES ('<1@example>', 'a@example', '2026-01-01T00:00:00+00:00')
                    """
                )

            database = EmailDatabase(path)
            database.initialize()

            with sqlite3.connect(path) as connection:
                row = connection.execute(
                    """
                    SELECT tracking_status, status_changed_at,
                           mailbox, uidvalidity, uid, last_imap_checked_at
                    FROM emails WHERE message_id = '<1@example>'
                    """
                ).fetchone()
            self.assertEqual(
                row,
                (
                    "active",
                    "2026-01-01T00:00:00+00:00",
                    None,
                    None,
                    None,
                    None,
                ),
            )

    def test_tracking_status_updates_status_changed_only_on_transition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            message = EmailMessage("<1@example>", "a@example", None, None, None, None)
            database.synchronize([message])

            self.assertTrue(
                database.update_tracking_status(
                    message.message_id,
                    TrackingStatus.INACTIVE_UNSTARRED,
                    checked_at="2026-08-08T00:00:00+00:00",
                )
            )
            self.assertFalse(
                database.update_tracking_status(
                    message.message_id,
                    TrackingStatus.INACTIVE_UNSTARRED,
                    checked_at="2026-08-09T00:00:00+00:00",
                )
            )

            with sqlite3.connect(path) as connection:
                row = connection.execute(
                    """
                    SELECT tracking_status, status_changed_at,
                           last_imap_checked_at
                    FROM emails WHERE message_id = ?
                    """,
                    (message.message_id,),
                ).fetchone()
            self.assertEqual(
                row,
                (
                    "inactive_unstarred",
                    "2026-08-08T00:00:00+00:00",
                    "2026-08-09T00:00:00+00:00",
                ),
            )

    def test_imap_identity_is_unique(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            first = EmailMessage("<1@example>", "a@example", None, None, None, None)
            second = EmailMessage("<2@example>", "b@example", None, None, None, None)
            database.synchronize([first, second])
            database.set_imap_identity(first.message_id, "INBOX", 10, 20)
            with self.assertRaises(sqlite3.IntegrityError):
                database.set_imap_identity(second.message_id, "INBOX", 10, 20)


if __name__ == "__main__":
    unittest.main()
