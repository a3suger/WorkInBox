from __future__ import annotations

import logging
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
_ACTION_READY = "wib-action-ready"
_BULK = "wib-bulk"
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
        ordered = [*self.in_reply_to, *reversed(self.references)]
        return tuple(dict.fromkeys(ordered))


@dataclass(frozen=True, slots=True)
class TriageMessage:
    email: EmailMessage
    headers: TriageHeaders
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TriageFetchResult:
    messages: tuple[TriageMessage, ...]
    uidvalidity: int
    highest_existing_uid: int


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
    def fetch_unread(
        self,
        checkpoint: tuple[int, int] | None = None,
    ) -> TriageFetchResult: ...

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
    origin_message_id = normalize_message_id(
        message.get("X-WorkInBox-Origin-Message-ID")
    ) or normalize_message_id(message.get("X-Forwarded-Message-Id"))
    return TriageHeaders(
        from_address=normalize_address(message.get("From")),
        message_id=normalize_message_id(message.get("Message-ID")),
        in_reply_to=parse_message_id_list(message.get("In-Reply-To")),
        references=parse_message_id_list(message.get("References")),
        origin_message_id=origin_message_id,
    )


class TriageService:
    """Apply deterministic TriageBox transitions in mailbox arrival order."""

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
            logging.info("TriageBox skipped: identity is not configured")
            return TriageResult()

        logging.info(
            "TriageBox starting: mailbox=%s lookback_days=%d",
            self.config.imap.mailbox,
            self.config.imap.new_mail_lookback_days,
        )
        self.relations.initialize()
        checkpoint = self.relations.checkpoint(self.config.imap.mailbox)
        if checkpoint is None:
            logging.info("TriageBox checkpoint: none")
        else:
            logging.info(
                "TriageBox checkpoint: uidvalidity=%d last_uid=%d",
                checkpoint[0],
                checkpoint[1],
            )
        try:
            fetched = self.imap_client.fetch_unread(checkpoint)
        except (OSError, RuntimeError, ValueError) as exc:
            logging.warning("TriageBox unread fetch failed: %s", exc)
            return TriageResult(errors=(TriageError("<mailbox>", str(exc)),))

        unread = fetched.messages
        logging.info(
            "TriageBox will process %d unread candidate messages oldest-first",
            len(unread),
        )
        errors: list[TriageError] = []
        support_requests = 0
        waiting_action_replies = 0

        for index, item in enumerate(unread, start=1):
            kind = sender_kind(item.email.sender, identity.all_addresses)
            logging.info(
                "TriageBox message %d/%d: uid=%s message_id=%s sender_kind=%s",
                index,
                len(unread),
                item.email.uid,
                item.email.message_id,
                kind,
            )
            try:
                if kind == TriageSenderKind.SELF:
                    if self._handle_self_support_request(item):
                        support_requests += 1
                elif self._handle_waiting_action_reply(item):
                    waiting_action_replies += 1
            except (OSError, RuntimeError, ValueError) as exc:
                logging.warning(
                    "TriageBox failed for %s: %s",
                    item.email.message_id,
                    exc,
                )
                errors.append(self._error(item, exc))

        if errors:
            logging.warning(
                "TriageBox checkpoint not advanced because %d message error(s) occurred",
                len(errors),
            )
        else:
            self.relations.save_checkpoint(
                self.config.imap.mailbox,
                fetched.uidvalidity,
                fetched.highest_existing_uid,
            )
            logging.info(
                "TriageBox checkpoint advanced: uidvalidity=%d last_uid=%d",
                fetched.uidvalidity,
                fetched.highest_existing_uid,
            )

        logging.info(
            "TriageBox finished: scanned=%d support_requests=%d waiting_action_replies=%d errors=%d",
            len(unread),
            support_requests,
            waiting_action_replies,
            len(errors),
        )
        return TriageResult(
            scanned=len(unread),
            support_requests=support_requests,
            waiting_action_replies=waiting_action_replies,
            errors=tuple(errors),
        )

    def _handle_self_support_request(self, item: TriageMessage) -> bool:
        origin_message_id = item.headers.origin_message_id
        if origin_message_id is None:
            logging.info("TriageBox self mail: no origin header; no transition")
            return False
        if self.relations.relation_kind_for(item.email.message_id) == _SUPPORT_REQUEST_REPLIED:
            logging.info("TriageBox self mail: support request already replied; no reactivation")
            return False

        logging.info(
            "TriageBox self mail: resolving origin message_id=%s",
            origin_message_id,
        )
        origin = self.imap_client.find_message_by_message_id(origin_message_id)
        if origin is None:
            logging.info("TriageBox self mail: origin was not found")
            return False
        origin_flags = set(origin.flags)
        if _SCHEDULE not in origin_flags:
            logging.info("TriageBox self mail: origin lacks required schedule state")
            return False

        self._set_keyword(origin, _REQUESTED, enabled=True)
        self._set_keyword(item, _WAITING_ACTION, enabled=True)
        self._set_flagged(item, enabled=True)
        self.relations.record(
            item.email.message_id,
            origin_message_id,
            _SUPPORT_REQUEST,
        )
        logging.info(
            "TriageBox self mail: marked origin requested and support request waiting-action/starred: %s",
            item.email.message_id,
        )
        return True

    def _handle_waiting_action_reply(self, item: TriageMessage) -> bool:
        logging.info(
            "TriageBox incoming mail: checking %d reply references",
            len(item.headers.referenced_message_ids),
        )
        waiting_message = self._resolve_waiting_action(item)
        if waiting_message is None:
            logging.info("TriageBox incoming mail: no waiting-action relation found")
            return False

        origin_message_id = (
            self.relations.origin_for(waiting_message.email.message_id)
            or waiting_message.headers.origin_message_id
        )
        # 対応待ちは、支援者への依頼を行った履歴として M2 に残す。
        self._set_keyword(waiting_message, _BULK, enabled=True)
        self._set_flagged(waiting_message, enabled=False)
        self._set_keyword(item, _ACTION_READY, enabled=True)
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
        logging.info(
            "TriageBox incoming mail: archived support request attention and marked reply action-ready: request=%s reply=%s",
            waiting_message.email.message_id,
            item.email.message_id,
        )
        return True

    def _resolve_waiting_action(self, item: TriageMessage) -> TriageMessage | None:
        for message_id in item.headers.referenced_message_ids:
            relation_kind = self.relations.relation_kind_for(message_id)
            if relation_kind != _SUPPORT_REQUEST:
                logging.info(
                    "TriageBox reply resolution: skipping untracked reference message_id=%s relation_kind=%s",
                    message_id,
                    relation_kind or "<none>",
                )
                continue
            logging.info(
                "TriageBox reply resolution: resolving tracked support request message_id=%s",
                message_id,
            )
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
