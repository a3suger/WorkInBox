from __future__ import annotations

import re
from dataclasses import dataclass
from email.message import Message
from email.utils import parseaddr
from enum import StrEnum


_MESSAGE_ID_RE = re.compile(r"<[^<>\s]+>")


class TriageSenderKind(StrEnum):
    SELF = "self"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class TriageHeaders:
    from_address: str | None
    message_id: str | None
    in_reply_to: tuple[str, ...]
    references: tuple[str, ...]
    origin_message_id: str | None

    @property
    def referenced_message_ids(self) -> tuple[str, ...]:
        """Return relation candidates in deterministic resolution order.

        In-Reply-To is checked first because it normally identifies the direct
        parent. References is then checked newest-first so the closest known
        ancestor is preferred. Duplicate Message-IDs are removed while
        preserving that priority.
        """
        ordered = [*self.in_reply_to, *reversed(self.references)]
        return tuple(dict.fromkeys(ordered))


def normalize_address(value: str | None) -> str | None:
    if value is None:
        return None
    _, address = parseaddr(value)
    normalized = address.strip().lower()
    return normalized or None


def normalize_message_id(value: str | None) -> str | None:
    if value is None:
        return None
    ids = parse_message_id_list(value)
    return ids[0] if ids else None


def parse_message_id_list(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()

    matches = _MESSAGE_ID_RE.findall(value)
    if matches:
        return tuple(dict.fromkeys(match.strip() for match in matches))

    # Be tolerant of non-conforming but common single bare Message-ID values.
    bare = value.strip()
    if not bare or any(character.isspace() for character in bare):
        return ()
    if bare.startswith("<") or bare.endswith(">"):
        return ()
    return (f"<{bare}>",)


def sender_kind(from_header: str | None, self_addresses: tuple[str, ...]) -> TriageSenderKind:
    sender = normalize_address(from_header)
    normalized_self = {
        normalized
        for value in self_addresses
        if (normalized := normalize_address(value)) is not None
    }
    if sender is not None and sender in normalized_self:
        return TriageSenderKind.SELF
    return TriageSenderKind.OTHER


def parse_triage_headers(message: Message) -> TriageHeaders:
    return TriageHeaders(
        from_address=normalize_address(message.get("From")),
        message_id=normalize_message_id(message.get("Message-ID")),
        in_reply_to=parse_message_id_list(message.get("In-Reply-To")),
        references=parse_message_id_list(message.get("References")),
        origin_message_id=normalize_message_id(
            message.get("X-WorkInBox-Origin-Message-ID")
        ),
    )
