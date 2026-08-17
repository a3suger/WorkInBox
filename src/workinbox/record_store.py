from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Record:
    id: int
    source_message_id: str
    source_account: str
    title: str
    summary: str
    note: str
    created_at: str
    updated_at: str


class RecordStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_message_id TEXT NOT NULL,
                    source_account TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS records_source_message
                ON records (source_message_id, id)
                """
            )

    def create(
        self,
        source_message_id: str,
        source_account: str,
        title: str,
        *,
        summary: str = "",
        note: str = "",
    ) -> Record:
        self.initialize()
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO records (
                    source_message_id, source_account, title, summary, note,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_message_id,
                    source_account,
                    title,
                    summary,
                    note,
                    now,
                    now,
                ),
            )
            record_id = int(cursor.lastrowid)
        record = self.get(record_id)
        if record is None:
            raise RuntimeError("failed to read inserted Record")
        return record

    def get(self, record_id: int) -> Record | None:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT id, source_message_id, source_account, title, summary,
                       note, created_at, updated_at
                FROM records
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()
        return self._from_row(row)

    def list(self) -> list[Record]:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                """
                SELECT id, source_message_id, source_account, title, summary,
                       note, created_at, updated_at
                FROM records
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
        return [record for row in rows if (record := self._from_row(row)) is not None]

    def delete(self, record_id: int) -> None:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            connection.execute("DELETE FROM records WHERE id = ?", (record_id,))

    @staticmethod
    def _from_row(row: tuple[object, ...] | None) -> Record | None:
        if row is None:
            return None
        return Record(
            id=int(row[0]),
            source_message_id=str(row[1]),
            source_account=str(row[2]),
            title=str(row[3]),
            summary=str(row[4]),
            note=str(row[5]),
            created_at=str(row[6]),
            updated_at=str(row[7]),
        )
