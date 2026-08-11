from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class TriageRelationStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS triage_relations (
                    message_id TEXT PRIMARY KEY,
                    origin_message_id TEXT NOT NULL,
                    relation_kind TEXT NOT NULL,
                    related_message_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS triage_relations_origin
                ON triage_relations (origin_message_id, relation_kind)
                """
            )

    def record(
        self,
        message_id: str,
        origin_message_id: str,
        relation_kind: str,
        *,
        related_message_id: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO triage_relations (
                    message_id, origin_message_id, relation_kind,
                    related_message_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    origin_message_id = excluded.origin_message_id,
                    relation_kind = excluded.relation_kind,
                    related_message_id = excluded.related_message_id,
                    updated_at = excluded.updated_at
                """,
                (
                    message_id,
                    origin_message_id,
                    relation_kind,
                    related_message_id,
                    now,
                    now,
                ),
            )

    def origin_for(self, message_id: str) -> str | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT origin_message_id
                FROM triage_relations
                WHERE message_id = ?
                """,
                (message_id,),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def relation_kind_for(self, message_id: str) -> str | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT relation_kind
                FROM triage_relations
                WHERE message_id = ?
                """,
                (message_id,),
            ).fetchone()
        return str(row[0]) if row is not None else None
