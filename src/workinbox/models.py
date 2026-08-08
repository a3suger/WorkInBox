from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TrackingStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE_UNSTARRED = "inactive_unstarred"
    INACTIVE_MOVED = "inactive_moved"


@dataclass(frozen=True, slots=True)
class EmailMessage:
    message_id: str
    sender: str
    recipients: str | None
    subject: str | None
    received_at: str | None
    body: str | None
