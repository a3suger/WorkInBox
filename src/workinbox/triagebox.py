from __future__ import annotations

import re
from dataclasses import dataclass
from email.message import Message
from email.utils import parseaddr
from enum import StrEnum
from typing import Protocol

from .config import AppConfig
from .models import EmailMessage, ImapFlagsSnapshot
from .triage_store import TriageRelationStore


_MESSAGE_ID_RE = re.compile(r"<[^<>\s]+>")
_WAITING_ACTION = "wib-waiting-action"
_SCHEDULE = "wib-schedule"
_REQUESTED = "wib-requested"
_SUPPORT_REQUEST = "schedule_support_request"
_SUPPORT_REQUEST_REPLIED = "schedule_support_request_replied"
_SUPPORT_REPLY = "schedule_support_reply"


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


@dataclass(frozen=True, slots=True)
class TriageMessage:
    email: EmailMessage
    headers: TriageHeaders
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TriageError:
    message_id: str
    message: str


@dataclass(frozen=True, slots=True)
class TriageResult:
    scanned: int = 0
    support_requests: int = 0
    waiting_action_replies: int = 0
    errors: tuple[TriageError, ...] = ()


class TriageImapClient(Protocol):
    def fetch_unread(self) -> list[TriageMessage]: ...

    def find_message_by_message_id(self, message_id: str) -> TriageMessage | None: ...

    def set_keyword(
        self,
        uid: int,
        keyword: str,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot: ...

    def set_flagged(
        self,
        uid: int,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot: ...


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


class TriageService:
    """Apply the deterministic v0.2 TriageBox transitions.

    This stage intentionally handles only relationships that can be decided
    from headers plus existing IMAP state. AI advertisement classification and
    ordinary self-sent reply-waiting decisions remain outside this service.
    """

    def __init__(
        self,
        config: AppConfig,
        imap_client: TriageImapClient,
        *,
        relation_store: TriageRelationStore | None = None,
    ) -> None:
        self.config = config
        self.imap_client = imap_client
        self.relations = relation_store or TriageRelationStore(config.database.path)

    def run(self) -> TriageResult:
        identity = self.config.identity
        if identity is None:
            return TriageResult()

        self.relations.initialize()
        try:
            unread = self.imap_client.fetch_unread()
        except (OSError, RuntimeError, ValueError) as exc:
            return TriageResult(errors=(TriageError("<mailbox>", str(exc)),))

        errors: list[TriageError] = []
        support_requests = 0
        waiting_action_replies = 0

        # Pass 1: establish WIB-created self-sent support requests first. This
        # lets a reply that is already in the unread set resolve against the
        # waiting request in the same TriageBox run. A request whose reply has
        # already arrived is not reactivated even if the request remains unread.
        for item in unread:
            if sender_kind(item.email.sender, identity.all_addresses) != TriageSenderKind.SELF:
                continue
            origin_message_id = item.headers.origin_message_id
            if origin_message_id is None:
                continue
            if self.relations.relation_kind_for(item.email.message_id) == _SUPPORT_REQUEST_REPLIED:
                continue
            try:
                origin = self.imap_client.find_message_by_message_id(origin_message_id)
                if origin is None:
                    continue
                origin_flags = set(origin.flags)
                if _SCHEDULE not in origin_flags or _REQUESTED not in origin_flags:
                    continue
                self._set_keyword(item, _WAITING_ACTION, enabled=True)
                self._set_flagged(item, enabled=True)
                self.relations.record(
                    item.email.message_id,
                    origin_message_id,
                    _SUPPORT_REQUEST,
                )
                support_requests += 1
            except (OSError, RuntimeError, ValueError) as exc:
                errors.append(self._error(item, exc))

        # Pass 2: resolve replies to tracked waiting-action messages. The old
        # request stops being the focus; the new reply becomes the schedule
        # work item so normal AI classification does not reinterpret it.
        for item in unread:
            if sender_kind(item.email.sender, identity.all_addresses) == TriageSenderKind.SELF:
                continue
            try:
                waiting_message = self._resolve_waiting_action(item)
                if waiting_message is None:
                    continue
                origin_message_id = (
                    self.relations.origin_for(waiting_message.email.message_id)
                    or waiting_message.headers.origin_message_id
                )
                self._set_keyword(waiting_message, _WAITING_ACTION, enabled=False)
                self._set_flagged(waiting_message, enabled=False)
                self._set_keyword(item, _SCHEDULE, enabled=True)
                self._set_flagged(item, enabled=True)
                if origin_message_id is not None:
                    self.relations.record(
                        waiting_message.email.message_id,
                        origin_message_id,
                        _SUPPORT_REQUEST_REPLIED,
                        related_message_id=item.email.message_id,
                    )
                    self.relations.record(
                        item.email.message_id,
                        origin_message_id,
                        _SUPPORT_REPLY,
                        related_message_id=waiting_message.email.message_id,
                    )
                waiting_action_replies += 1
            except (OSError, RuntimeError, ValueError) as exc:
                errors.append(self._error(item, exc))

        return TriageResult(
            scanned=len(unread),
            support_requests=support_requests,
            waiting_action_replies=waiting_action_replies,
            errors=tuple(errors),
        )

    def _resolve_waiting_action(self, item: TriageMessage) -> TriageMessage | None:
        for message_id in item.headers.referenced_message_ids:
            referenced = self.imap_client.find_message_by_message_id(message_id)
            if referenced is not None and _WAITING_ACTION in referenced.flags:
                return referenced
        return None

    def _set_keyword(self, item: TriageMessage, keyword: str, *, enabled: bool) -> None:
        if item.email.uid is None:
            raise RuntimeError("TriageBox message UID is unavailable")
        self.imap_client.set_keyword(
            item.email.uid,
            keyword,
            enabled=enabled,
            expected_uidvalidity=item.email.uidvalidity,
        )

    def _set_flagged(self, item: TriageMessage, *, enabled: bool) -> None:
        if item.email.uid is None:
            raise RuntimeError("TriageBox message UID is unavailable")
        self.imap_client.set_flagged(
            item.email.uid,
            enabled=enabled,
            expected_uidvalidity=item.email.uidvalidity,
        )

    @staticmethod
    def _error(item: TriageMessage, exc: BaseException) -> TriageError:
        return TriageError(item.email.message_id, str(exc))
