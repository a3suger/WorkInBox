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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dedicated_workflow_focus (
                    workflow_origin_message_id TEXT PRIMARY KEY,
                    current_focus_message_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS dedicated_workflow_current_focus
                ON dedicated_workflow_focus (current_focus_message_id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS triage_checkpoints (
                    mailbox TEXT PRIMARY KEY,
                    uidvalidity INTEGER NOT NULL,
                    last_uid INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
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

    def ensure_workflow_focus(self, workflow_origin_message_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO dedicated_workflow_focus (
                    workflow_origin_message_id, current_focus_message_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(workflow_origin_message_id) DO NOTHING
                """,
                (
                    workflow_origin_message_id,
                    workflow_origin_message_id,
                    now,
                    now,
                ),
            )

    def set_current_focus(
        self,
        workflow_origin_message_id: str,
        current_focus_message_id: str,
    ) -> None:
        self.ensure_workflow_focus(workflow_origin_message_id)
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                UPDATE dedicated_workflow_focus
                SET current_focus_message_id = ?, updated_at = ?
                WHERE workflow_origin_message_id = ?
                """,
                (
                    current_focus_message_id,
                    now,
                    workflow_origin_message_id,
                ),
            )

    def current_focus_for(self, workflow_origin_message_id: str) -> str | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT current_focus_message_id
                FROM dedicated_workflow_focus
                WHERE workflow_origin_message_id = ?
                """,
                (workflow_origin_message_id,),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def workflow_origin_for_focus(self, current_focus_message_id: str) -> str | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT workflow_origin_message_id
                FROM dedicated_workflow_focus
                WHERE current_focus_message_id = ?
                """,
                (current_focus_message_id,),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def checkpoint(self, mailbox: str) -> tuple[int, int] | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT uidvalidity, last_uid
                FROM triage_checkpoints
                WHERE mailbox = ?
                """,
                (mailbox,),
            ).fetchone()
        if row is None:
            return None
        return int(row[0]), int(row[1])

    def save_checkpoint(self, mailbox: str, uidvalidity: int, last_uid: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO triage_checkpoints (mailbox, uidvalidity, last_uid, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(mailbox) DO UPDATE SET
                    uidvalidity = excluded.uidvalidity,
                    last_uid = excluded.last_uid,
                    updated_at = excluded.updated_at
                """,
                (mailbox, uidvalidity, last_uid, now),
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
