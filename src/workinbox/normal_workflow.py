from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig
from .database import EmailDatabase
from .imap_client import ImapClient
from .models import TrackingStatus
from .record_store import Record, RecordStore


_NORMAL_TAGS = frozenset({"wib-answer", "wib-review", "wib-watch"})
_BULK = "wib-bulk"


@dataclass(frozen=True, slots=True)
class NormalWorkflowCompletion:
    message_id: str
    saved_record: Record | None


class NormalWorkflowCompletionService:
    def __init__(
        self,
        config: AppConfig,
        *,
        database: EmailDatabase | None = None,
        imap_client: ImapClient | None = None,
        record_store: RecordStore | None = None,
    ) -> None:
        self.config = config
        self.database = database or EmailDatabase(config.database.path)
        self.imap_client = imap_client or ImapClient(config.imap)
        self.records = record_store or RecordStore(config.database.path)

    def complete(self, message_id: str) -> NormalWorkflowCompletion:
        message, reference, flags = self._validated_target(message_id)
        del message
        del flags

        self.imap_client.set_keyword(
            reference.uid,
            _BULK,
            enabled=True,
            expected_uidvalidity=reference.uidvalidity,
        )
        try:
            self.imap_client.set_flagged(
                reference.uid,
                enabled=False,
                expected_uidvalidity=reference.uidvalidity,
            )
        except (OSError, RuntimeError, ValueError):
            try:
                self.imap_client.set_keyword(
                    reference.uid,
                    _BULK,
                    enabled=False,
                    expected_uidvalidity=reference.uidvalidity,
                )
            except (OSError, RuntimeError, ValueError):
                pass
            raise

        self.database.update_tracking_status(
            message_id,
            TrackingStatus.INACTIVE_UNSTARRED,
        )
        return NormalWorkflowCompletion(message_id, None)

    def save_record_and_complete(
        self,
        message_id: str,
        *,
        title: str = "",
        summary: str = "",
        note: str = "",
    ) -> NormalWorkflowCompletion:
        message, reference, flags = self._validated_target(message_id)
        normalized_title = title.strip() or (message.subject or "(件名なし)")
        had_bulk = _BULK in flags

        record = self.records.create(
            message_id,
            self.config.imap.username,
            normalized_title,
            summary=summary.strip(),
            note=note.strip(),
        )
        try:
            if had_bulk:
                self.imap_client.set_keyword(
                    reference.uid,
                    _BULK,
                    enabled=False,
                    expected_uidvalidity=reference.uidvalidity,
                )
            self.imap_client.set_flagged(
                reference.uid,
                enabled=False,
                expected_uidvalidity=reference.uidvalidity,
            )
        except (OSError, RuntimeError, ValueError):
            self.records.delete(record.id)
            if had_bulk:
                try:
                    self.imap_client.set_keyword(
                        reference.uid,
                        _BULK,
                        enabled=True,
                        expected_uidvalidity=reference.uidvalidity,
                    )
                except (OSError, RuntimeError, ValueError):
                    pass
            raise

        self.database.update_tracking_status(
            message_id,
            TrackingStatus.INACTIVE_UNSTARRED,
        )
        return NormalWorkflowCompletion(message_id, record)

    def _validated_target(self, message_id: str):
        self.database.initialize()
        self.records.initialize()
        message = self.database.email_message(message_id)
        if message is None:
            raise ValueError(f"Unknown source message: {message_id}")
        reference = self.database.imap_reference(message_id)
        if reference is None:
            raise ValueError("IMAP identity is unavailable")
        if reference.mailbox != self.config.imap.mailbox:
            raise ValueError(f"mailbox mismatch: {reference.mailbox}")
        snapshot = self.imap_client.inspect_flags(
            reference.uid,
            expected_uidvalidity=reference.uidvalidity,
        )
        if not _NORMAL_TAGS.intersection(snapshot.flags):
            raise ValueError("message is not in a normal workflow")
        return message, reference, frozenset(snapshot.flags)
