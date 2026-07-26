from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from .models import EmailMessage


class EmailDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS emails (
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

    def message_ids(self) -> set[str]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute("SELECT message_id FROM emails")
            return {str(row[0]) for row in rows}

    def synchronize(self, messages: Iterable[EmailMessage]) -> tuple[int, int]:
        incoming = {message.message_id: message for message in messages}
        existing = self.message_ids()
        added_ids = incoming.keys() - existing
        removed_ids = existing - incoming.keys()
        synchronized_at = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.path) as connection:
            connection.executemany(
                """
                INSERT INTO emails (
                    message_id, sender, recipients, subject,
                    received_at, body, synchronized_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        incoming[message_id].message_id,
                        incoming[message_id].sender,
                        incoming[message_id].recipients,
                        incoming[message_id].subject,
                        incoming[message_id].received_at,
                        incoming[message_id].body,
                        synchronized_at,
                    )
                    for message_id in added_ids
                ],
            )
            connection.executemany(
                "DELETE FROM emails WHERE message_id = ?",
                [(message_id,) for message_id in removed_ids],
            )
        return len(added_ids), len(removed_ids)
