from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from .models import (
    Deadline,
    DeadlineCandidate,
    DeadlineCandidateStatus,
    DeadlineCreatedBy,
    EmailMessage,
    ImapReference,
    TrackedEmail,
    TrackingStatus,
)


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
                    synchronized_at TEXT NOT NULL,
                    mailbox TEXT,
                    uidvalidity INTEGER,
                    uid INTEGER,
                    tracking_status TEXT NOT NULL DEFAULT 'active',
                    status_changed_at TEXT,
                    last_imap_checked_at TEXT
                )
                """
            )
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(emails)")
            }
            migrations = {
                "mailbox": "ALTER TABLE emails ADD COLUMN mailbox TEXT",
                "uidvalidity": "ALTER TABLE emails ADD COLUMN uidvalidity INTEGER",
                "uid": "ALTER TABLE emails ADD COLUMN uid INTEGER",
                "tracking_status": (
                    "ALTER TABLE emails ADD COLUMN tracking_status TEXT "
                    "NOT NULL DEFAULT 'active'"
                ),
                "status_changed_at": (
                    "ALTER TABLE emails ADD COLUMN status_changed_at TEXT"
                ),
                "last_imap_checked_at": (
                    "ALTER TABLE emails ADD COLUMN last_imap_checked_at TEXT"
                ),
            }
            for column, statement in migrations.items():
                if column not in columns:
                    connection.execute(statement)
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS emails_imap_identity
                ON emails (mailbox, uidvalidity, uid)
                WHERE mailbox IS NOT NULL
                  AND uidvalidity IS NOT NULL
                  AND uid IS NOT NULL
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS deadline_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_message_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    due_at TEXT,
                    source_text TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_by TEXT NOT NULL,
                    needs_review INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (source_message_id) REFERENCES emails(message_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS deadline_candidates_message
                ON deadline_candidates (source_message_id, id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS deadlines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_message_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    timezone TEXT,
                    description TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (source_message_id) REFERENCES emails(message_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS deadlines_message
                ON deadlines (source_message_id, id)
                """
            )
            connection.execute(
                """
                UPDATE emails
                SET status_changed_at = COALESCE(status_changed_at, synchronized_at)
                WHERE status_changed_at IS NULL
                """
            )

    def message_ids(self) -> set[str]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute("SELECT message_id FROM emails")
            return {str(row[0]) for row in rows}

    def email_message(self, message_id: str) -> EmailMessage | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT message_id, sender, recipients, subject, received_at, body,
                       mailbox, uidvalidity, uid
                FROM emails
                WHERE message_id = ?
                """,
                (message_id,),
            ).fetchone()
        if row is None:
            return None
        return EmailMessage(
            message_id=str(row[0]),
            sender=str(row[1]),
            recipients=str(row[2]) if row[2] is not None else None,
            subject=str(row[3]) if row[3] is not None else None,
            received_at=str(row[4]) if row[4] is not None else None,
            body=str(row[5]) if row[5] is not None else None,
            mailbox=str(row[6]) if row[6] is not None else None,
            uidvalidity=int(row[7]) if row[7] is not None else None,
            uid=int(row[8]) if row[8] is not None else None,
        )

    def list_tracked_emails(
        self,
        *,
        active: bool,
    ) -> list[TrackedEmail]:
        if active:
            condition = "tracking_status = ?"
            parameters: tuple[object, ...] = (TrackingStatus.ACTIVE.value,)
        else:
            condition = "tracking_status != ?"
            parameters = (TrackingStatus.ACTIVE.value,)

        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                f"""
                SELECT message_id, sender, subject, received_at,
                       tracking_status, status_changed_at, last_imap_checked_at,
                       mailbox, uidvalidity, uid
                FROM emails
                WHERE {condition}
                ORDER BY received_at DESC, id DESC
                """,
                parameters,
            ).fetchall()
        return [
            TrackedEmail(
                message_id=str(row[0]),
                sender=str(row[1]),
                subject=str(row[2]) if row[2] is not None else None,
                received_at=str(row[3]) if row[3] is not None else None,
                tracking_status=TrackingStatus(str(row[4])),
                status_changed_at=str(row[5]) if row[5] is not None else None,
                last_imap_checked_at=str(row[6]) if row[6] is not None else None,
                mailbox=str(row[7]) if row[7] is not None else None,
                uidvalidity=int(row[8]) if row[8] is not None else None,
                uid=int(row[9]) if row[9] is not None else None,
            )
            for row in rows
        ]

    def imap_references(
        self,
        mailbox: str,
        *,
        include_inactive: bool = False,
    ) -> list[ImapReference]:
        query = """
            SELECT message_id, mailbox, uidvalidity, uid
            FROM emails
            WHERE mailbox = ?
              AND uidvalidity IS NOT NULL
              AND uid IS NOT NULL
        """
        parameters: list[object] = [mailbox]
        if not include_inactive:
            query += " AND tracking_status = ?"
            parameters.append(TrackingStatus.ACTIVE.value)
        query += " ORDER BY id"

        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            ImapReference(
                message_id=str(row[0]),
                mailbox=str(row[1]),
                uidvalidity=int(row[2]),
                uid=int(row[3]),
            )
            for row in rows
        ]

    def imap_reference(self, message_id: str) -> ImapReference | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT message_id, mailbox, uidvalidity, uid
                FROM emails
                WHERE message_id = ?
                  AND mailbox IS NOT NULL
                  AND uidvalidity IS NOT NULL
                  AND uid IS NOT NULL
                """,
                (message_id,),
            ).fetchone()
        if row is None:
            return None
        return ImapReference(
            message_id=str(row[0]),
            mailbox=str(row[1]),
            uidvalidity=int(row[2]),
            uid=int(row[3]),
        )

    def active_imap_references(self, mailbox: str) -> list[ImapReference]:
        return self.imap_references(mailbox)

    def synchronize(self, messages: Iterable[EmailMessage]) -> tuple[int, int]:
        incoming = {message.message_id: message for message in messages}
        synchronized_at = datetime.now(timezone.utc).isoformat()
        added = 0
        reactivated = 0

        with sqlite3.connect(self.path) as connection:
            for message in incoming.values():
                row = connection.execute(
                    "SELECT tracking_status FROM emails WHERE message_id = ?",
                    (message.message_id,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO emails (
                            message_id, sender, recipients, subject,
                            received_at, body, synchronized_at,
                            mailbox, uidvalidity, uid,
                            tracking_status, status_changed_at,
                            last_imap_checked_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            message.message_id,
                            message.sender,
                            message.recipients,
                            message.subject,
                            message.received_at,
                            message.body,
                            synchronized_at,
                            message.mailbox,
                            message.uidvalidity,
                            message.uid,
                            TrackingStatus.ACTIVE.value,
                            synchronized_at,
                            synchronized_at,
                        ),
                    )
                    added += 1
                    continue

                current_status = str(row[0])
                next_changed_at = (
                    synchronized_at
                    if current_status != TrackingStatus.ACTIVE.value
                    else None
                )
                connection.execute(
                    """
                    UPDATE emails
                    SET sender = ?, recipients = ?, subject = ?,
                        received_at = ?, body = ?, synchronized_at = ?,
                        mailbox = COALESCE(?, mailbox),
                        uidvalidity = COALESCE(?, uidvalidity),
                        uid = COALESCE(?, uid),
                        tracking_status = ?,
                        status_changed_at = COALESCE(?, status_changed_at),
                        last_imap_checked_at = ?
                    WHERE message_id = ?
                    """,
                    (
                        message.sender,
                        message.recipients,
                        message.subject,
                        message.received_at,
                        message.body,
                        synchronized_at,
                        message.mailbox,
                        message.uidvalidity,
                        message.uid,
                        TrackingStatus.ACTIVE.value,
                        next_changed_at,
                        synchronized_at,
                        message.message_id,
                    ),
                )
                if current_status != TrackingStatus.ACTIVE.value:
                    reactivated += 1
        return added, reactivated

    def set_imap_identity(
        self,
        message_id: str,
        mailbox: str,
        uidvalidity: int,
        uid: int,
    ) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                UPDATE emails
                SET mailbox = ?, uidvalidity = ?, uid = ?
                WHERE message_id = ?
                """,
                (mailbox, uidvalidity, uid, message_id),
            )

    def update_tracking_status(
        self,
        message_id: str,
        status: TrackingStatus,
        *,
        checked_at: str | None = None,
    ) -> bool:
        now = checked_at or datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT tracking_status FROM emails WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                return False
            current = str(row[0])
            if current == status.value:
                connection.execute(
                    """
                    UPDATE emails
                    SET last_imap_checked_at = ?
                    WHERE message_id = ?
                    """,
                    (now, message_id),
                )
                return False
            connection.execute(
                """
                UPDATE emails
                SET tracking_status = ?, status_changed_at = ?,
                    last_imap_checked_at = ?
                WHERE message_id = ?
                """,
                (status.value, now, now, message_id),
            )
            return True

    def add_deadline_candidate(
        self,
        source_message_id: str,
        title: str,
        *,
        due_at: str | None = None,
        source_text: str | None = None,
        created_by: DeadlineCreatedBy = DeadlineCreatedBy.AI,
        needs_review: bool = False,
    ) -> DeadlineCandidate:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO deadline_candidates (
                    source_message_id, title, due_at, source_text, status,
                    created_by, needs_review, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_message_id,
                    title,
                    due_at,
                    source_text,
                    DeadlineCandidateStatus.PENDING.value,
                    created_by.value,
                    1 if needs_review else 0,
                    now,
                    now,
                ),
            )
            candidate_id = int(cursor.lastrowid)
        candidate = self.deadline_candidate(candidate_id)
        if candidate is None:
            raise RuntimeError("failed to read inserted deadline candidate")
        return candidate

    def deadline_candidate(self, candidate_id: int) -> DeadlineCandidate | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT id, source_message_id, title, due_at, source_text,
                       status, created_by, needs_review, created_at, updated_at
                FROM deadline_candidates
                WHERE id = ?
                """,
                (candidate_id,),
            ).fetchone()
        return self._deadline_candidate_from_row(row)

    def deadline_candidates(self, source_message_id: str) -> list[DeadlineCandidate]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                """
                SELECT id, source_message_id, title, due_at, source_text,
                       status, created_by, needs_review, created_at, updated_at
                FROM deadline_candidates
                WHERE source_message_id = ?
                ORDER BY id
                """,
                (source_message_id,),
            ).fetchall()
        return [
            candidate
            for row in rows
            if (candidate := self._deadline_candidate_from_row(row)) is not None
        ]

    def update_deadline_candidate(
        self,
        candidate_id: int,
        *,
        title: str,
        due_at: str | None,
        source_text: str | None,
        needs_review: bool,
    ) -> DeadlineCandidate:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                UPDATE deadline_candidates
                SET title = ?, due_at = ?, source_text = ?, needs_review = ?,
                    updated_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    title,
                    due_at,
                    source_text,
                    1 if needs_review else 0,
                    now,
                    candidate_id,
                    DeadlineCandidateStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("deadline candidate is missing or already resolved")
        candidate = self.deadline_candidate(candidate_id)
        if candidate is None:
            raise RuntimeError("failed to read updated deadline candidate")
        return candidate

    def reject_deadline_candidate(self, candidate_id: int) -> DeadlineCandidate:
        return self._set_deadline_candidate_status(
            candidate_id,
            DeadlineCandidateStatus.REJECTED,
        )

    def register_deadline_candidate(
        self,
        candidate_id: int,
        *,
        timezone_name: str | None = None,
        description: str | None = None,
    ) -> Deadline:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT source_message_id, title, due_at, created_by, status
                FROM deadline_candidates
                WHERE id = ?
                """,
                (candidate_id,),
            ).fetchone()
            if row is None:
                raise ValueError("deadline candidate does not exist")
            if str(row[4]) != DeadlineCandidateStatus.PENDING.value:
                raise ValueError("deadline candidate is already resolved")
            due_at = str(row[2]) if row[2] is not None else None
            if due_at is None:
                raise ValueError("deadline candidate due_at is required for registration")
            cursor = connection.execute(
                """
                INSERT INTO deadlines (
                    source_message_id, title, due_at, timezone, description,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row[0]),
                    str(row[1]),
                    due_at,
                    timezone_name,
                    description,
                    str(row[3]),
                    now,
                    now,
                ),
            )
            deadline_id = int(cursor.lastrowid)
            connection.execute(
                """
                UPDATE deadline_candidates
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (DeadlineCandidateStatus.REGISTERED.value, now, candidate_id),
            )
        deadline = self.deadline(deadline_id)
        if deadline is None:
            raise RuntimeError("failed to read registered deadline")
        return deadline

    def deadline(self, deadline_id: int) -> Deadline | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT id, source_message_id, title, due_at, timezone,
                       description, created_by, created_at, updated_at
                FROM deadlines
                WHERE id = ?
                """,
                (deadline_id,),
            ).fetchone()
        return self._deadline_from_row(row)

    def deadlines(self, source_message_id: str) -> list[Deadline]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                """
                SELECT id, source_message_id, title, due_at, timezone,
                       description, created_by, created_at, updated_at
                FROM deadlines
                WHERE source_message_id = ?
                ORDER BY due_at, id
                """,
                (source_message_id,),
            ).fetchall()
        return [
            deadline
            for row in rows
            if (deadline := self._deadline_from_row(row)) is not None
        ]

    def _set_deadline_candidate_status(
        self,
        candidate_id: int,
        status: DeadlineCandidateStatus,
    ) -> DeadlineCandidate:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                UPDATE deadline_candidates
                SET status = ?, updated_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    status.value,
                    now,
                    candidate_id,
                    DeadlineCandidateStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("deadline candidate is missing or already resolved")
        candidate = self.deadline_candidate(candidate_id)
        if candidate is None:
            raise RuntimeError("failed to read resolved deadline candidate")
        return candidate

    @staticmethod
    def _deadline_candidate_from_row(row: tuple[object, ...] | None) -> DeadlineCandidate | None:
        if row is None:
            return None
        return DeadlineCandidate(
            id=int(row[0]),
            source_message_id=str(row[1]),
            title=str(row[2]),
            due_at=str(row[3]) if row[3] is not None else None,
            source_text=str(row[4]) if row[4] is not None else None,
            status=DeadlineCandidateStatus(str(row[5])),
            created_by=DeadlineCreatedBy(str(row[6])),
            needs_review=bool(row[7]),
            created_at=str(row[8]),
            updated_at=str(row[9]),
        )

    @staticmethod
    def _deadline_from_row(row: tuple[object, ...] | None) -> Deadline | None:
        if row is None:
            return None
        return Deadline(
            id=int(row[0]),
            source_message_id=str(row[1]),
            title=str(row[2]),
            due_at=str(row[3]),
            timezone=str(row[4]) if row[4] is not None else None,
            description=str(row[5]) if row[5] is not None else None,
            created_by=DeadlineCreatedBy(str(row[6])),
            created_at=str(row[7]),
            updated_at=str(row[8]),
        )
