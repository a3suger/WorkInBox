from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .config import AppConfig
from .database import EmailDatabase
from .deadline_extractor import OllamaDeadlineExtractor
from .imap_client import ImapClient
from .models import DeadlineCreatedBy, TrackedEmail


@dataclass(frozen=True, slots=True)
class DeadlineExtractionError:
    message_id: str
    message: str


@dataclass(frozen=True, slots=True)
class DeadlineExtractionResult:
    checked: int
    eligible: int
    extracted_messages: int
    candidates_added: int
    errors: tuple[DeadlineExtractionError, ...]


class DeadlineExtractionService:
    def __init__(
        self,
        config: AppConfig,
        *,
        database: EmailDatabase | None = None,
        imap_client: ImapClient | None = None,
        extractor: OllamaDeadlineExtractor | None = None,
    ) -> None:
        self.config = config
        self.database = database or EmailDatabase(config.database.path)
        self.imap_client = imap_client or ImapClient(config.imap)
        self.extractor = extractor or OllamaDeadlineExtractor(config.ai)

    def extract_pending(self) -> DeadlineExtractionResult:
        self.database.initialize()
        self._initialize_extraction_state()

        checked = 0
        eligible = 0
        extracted_messages = 0
        candidates_added = 0
        errors: list[DeadlineExtractionError] = []

        for tracked in self.database.list_tracked_emails(active=True):
            if not self._has_imap_identity(tracked):
                continue
            if tracked.mailbox != self.config.imap.mailbox:
                continue

            checked += 1
            try:
                snapshot = self.imap_client.inspect_flags(
                    tracked.uid,
                    expected_uidvalidity=tracked.uidvalidity,
                )
            except (OSError, RuntimeError, ValueError) as exc:
                errors.append(DeadlineExtractionError(tracked.message_id, str(exc)))
                continue

            flags = set(snapshot.flags)
            if "wib-deadline" not in flags or "wib-deadline-done" in flags:
                continue
            if self._was_extracted(tracked.message_id):
                continue

            eligible += 1
            message = self.database.email_message(tracked.message_id)
            if message is None:
                errors.append(
                    DeadlineExtractionError(
                        tracked.message_id,
                        "email content is unavailable in SQLite",
                    )
                )
                continue

            try:
                extracted = self.extractor.extract(message)
                for item in extracted:
                    self.database.add_deadline_candidate(
                        tracked.message_id,
                        item.title,
                        due_at=item.due_at,
                        source_text=item.source_text,
                        created_by=DeadlineCreatedBy.AI,
                        needs_review=item.needs_review,
                    )
                    candidates_added += 1
                self._mark_extracted(tracked.message_id, len(extracted))
                extracted_messages += 1
            except (OSError, RuntimeError, ValueError) as exc:
                errors.append(DeadlineExtractionError(tracked.message_id, str(exc)))

        return DeadlineExtractionResult(
            checked=checked,
            eligible=eligible,
            extracted_messages=extracted_messages,
            candidates_added=candidates_added,
            errors=tuple(errors),
        )

    def reset_extraction(self, message_id: str) -> None:
        self.database.initialize()
        self._initialize_extraction_state()
        with sqlite3.connect(self.config.database.path) as connection:
            connection.execute(
                "DELETE FROM deadline_extractions WHERE source_message_id = ?",
                (message_id,),
            )

    @staticmethod
    def _has_imap_identity(tracked: TrackedEmail) -> bool:
        return (
            tracked.uid is not None
            and tracked.uidvalidity is not None
            and tracked.mailbox is not None
        )

    def _initialize_extraction_state(self) -> None:
        with sqlite3.connect(self.config.database.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS deadline_extractions (
                    source_message_id TEXT PRIMARY KEY,
                    extracted_at TEXT NOT NULL,
                    candidate_count INTEGER NOT NULL,
                    FOREIGN KEY (source_message_id) REFERENCES emails(message_id)
                )
                """
            )

    def _was_extracted(self, message_id: str) -> bool:
        with sqlite3.connect(self.config.database.path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM deadline_extractions
                WHERE source_message_id = ?
                """,
                (message_id,),
            ).fetchone()
        return row is not None

    def _mark_extracted(self, message_id: str, candidate_count: int) -> None:
        extracted_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.config.database.path) as connection:
            connection.execute(
                """
                INSERT INTO deadline_extractions (
                    source_message_id, extracted_at, candidate_count
                ) VALUES (?, ?, ?)
                ON CONFLICT(source_message_id) DO UPDATE SET
                    extracted_at = excluded.extracted_at,
                    candidate_count = excluded.candidate_count
                """,
                (message_id, extracted_at, candidate_count),
            )
