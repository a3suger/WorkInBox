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
    request_id: str | None = None
    request_message_id: str | None = None


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
            columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(records)")}
            if "request_id" not in columns:
                connection.execute("ALTER TABLE records ADD COLUMN request_id TEXT")
            if "request_message_id" not in columns:
                connection.execute("ALTER TABLE records ADD COLUMN request_message_id TEXT")
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS records_request_id ON records (request_id) WHERE request_id IS NOT NULL"
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
        request_id: str | None = None,
        request_message_id: str | None = None,
    ) -> Record:
        self.initialize()
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO records (
                    source_message_id, source_account, title, summary, note,
                    created_at, updated_at, request_id, request_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_message_id,
                    source_account,
                    title,
                    summary,
                    note,
                    now,
                    now,
                    request_id,
                    request_message_id,
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
                       note, created_at, updated_at, request_id, request_message_id
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
                       note, created_at, updated_at, request_id, request_message_id
                FROM records
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
        return [record for row in rows if (record := self._from_row(row)) is not None]

    def get_by_request_id(self, request_id: str) -> Record | None:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT id, source_message_id, source_account, title, summary,
                       note, created_at, updated_at, request_id, request_message_id
                FROM records WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
        return self._from_row(row)

    def pending_ai(self) -> list[Record]:
        return [record for record in self.list() if record.request_id and not record.summary]

    def update_summary(self, record_id: int, summary: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "UPDATE records SET summary = ?, updated_at = ? WHERE id = ?",
                (summary.strip(), now, record_id),
            )

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
            request_id=str(row[8]) if row[8] is not None else None,
            request_message_id=str(row[9]) if row[9] is not None else None,
        )
