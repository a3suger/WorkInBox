from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmailMessage:
    message_id: str
    sender: str
    recipients: str | None
    subject: str | None
    received_at: str | None
    body: str | None
