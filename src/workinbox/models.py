from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TrackingStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE_UNSTARRED = "inactive_unstarred"
    INACTIVE_MOVED = "inactive_moved"


class ImapCheckState(StrEnum):
    FLAGGED = "flagged"
    UNSTARRED = "unstarred"
    MISSING = "missing"
    ERROR = "error"


class DeadlineCandidateStatus(StrEnum):
    PENDING = "pending"
    REGISTERED = "registered"
    REJECTED = "rejected"


class DeadlineCreatedBy(StrEnum):
    AI = "ai"
    USER = "user"


@dataclass(frozen=True, slots=True)
class EmailMessage:
    message_id: str
    sender: str
    recipients: str | None
    subject: str | None
    received_at: str | None
    body: str | None
    mailbox: str | None = None
    uidvalidity: int | None = None
    uid: int | None = None


@dataclass(frozen=True, slots=True)
class TriageMessage:
    message_id: str
    sender: str
    recipients: str | None
    subject: str | None
    received_at: str | None
    origin_message_id: str | None
    in_reply_to: str | None
    references: tuple[str, ...]
    mailbox: str
    uidvalidity: int
    uid: int
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ImapReference:
    message_id: str
    mailbox: str
    uidvalidity: int
    uid: int


@dataclass(frozen=True, slots=True)
class ImapCheckResult:
    message_id: str
    state: ImapCheckState
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TrackedEmail:
    message_id: str
    sender: str
    subject: str | None
    received_at: str | None
    tracking_status: TrackingStatus
    status_changed_at: str | None
    last_imap_checked_at: str | None
    mailbox: str | None = None
    uidvalidity: int | None = None
    uid: int | None = None


@dataclass(frozen=True, slots=True)
class ImapFlagsSnapshot:
    mailbox: str
    uidvalidity: int
    uid: int
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeadlineCandidate:
    id: int
    source_message_id: str
    title: str
    due_at: str | None
    source_text: str | None
    status: DeadlineCandidateStatus
    created_by: DeadlineCreatedBy
    needs_review: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Deadline:
    id: int
    source_message_id: str
    title: str
    due_at: str
    timezone: str | None
    description: str | None
    created_by: DeadlineCreatedBy
    created_at: str
    updated_at: str
    start_at: str | None = None
    status: str = "NEEDS-ACTION"
    completed_at: str | None = None
    percent_complete: int = 0
    priority: int = 0
    version: int = 1
