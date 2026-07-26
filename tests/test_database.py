from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from workinbox.database import EmailDatabase
from workinbox.models import EmailMessage


class EmailDatabaseTest(unittest.TestCase):
    def test_add_and_remove_messages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()

            first = EmailMessage("<1@example>", "a@example", None, "One", None, "A")
            second = EmailMessage("<2@example>", "b@example", None, "Two", None, "B")

            self.assertEqual(database.synchronize([first, second]), (2, 0))
            self.assertEqual(database.synchronize([second]), (0, 1))

            with sqlite3.connect(path) as connection:
                rows = connection.execute(
                    "SELECT message_id FROM emails ORDER BY message_id"
                ).fetchall()
            self.assertEqual(rows, [("<2@example>",)])

    def test_duplicate_message_id_is_not_added_twice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = EmailDatabase(Path(directory) / "workinbox.db")
            database.initialize()
            message = EmailMessage("<1@example>", "a@example", None, None, None, None)
            self.assertEqual(database.synchronize([message]), (1, 0))
            self.assertEqual(database.synchronize([message]), (0, 0))


if __name__ == "__main__":
    unittest.main()
