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


@dataclass(frozen=True, slots=True)
class ImapFlagsSnapshot:
    mailbox: str
    uidvalidity: int
    uid: int
    flags: tuple[str, ...]
