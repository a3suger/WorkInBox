from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from email.message import Message
from email.utils import parseaddr
from enum import StrEnum
from typing import Protocol
from .sync_progress import ProgressCallback

from .config import AppConfig
from .models import EmailMessage, ImapFlagsSnapshot
from .triage_store import TriageRelationStore


_MESSAGE_ID_RE = re.compile(r"<[^<>\s]+>")
_WAITING_ACTION = "wib-waiting-action"
_ACTION_READY = "wib-action-ready"
_BULK = "wib-bulk"
_SCHEDULE = "wib-schedule"
_DEADLINE = "wib-deadline"
_SUPPORT_REQUEST = "schedule_support_request"
_SUPPORT_REQUEST_REPLIED = "schedule_support_request_replied"
_SUPPORT_REPLY = "schedule_support_reply"
_SUPPORT_RELATION_KINDS = {
    _SUPPORT_REQUEST,
    _SUPPORT_REQUEST_REPLIED,
    _SUPPORT_REPLY,
}
_DEDICATED_WORKFLOW_KEYS = {_SCHEDULE, _DEADLINE}


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
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.config = config
        self.imap_client = imap_client
        self.relations = relation_store or TriageRelationStore(config.database.path)
        self.progress_callback = progress_callback

    def _progress(self, **event: object) -> None:
        if self.progress_callback is not None:
            self.progress_callback(dict(event))

    def run(self) -> TriageResult:
        identity = self.config.identity
        if identity is None:
            self._progress(
                phase="triage",
                label="TriageBox: identity未設定のためスキップ",
                current=0,
                total=0,
                errors=0,
            )
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
        # Register dedicated workflow origins already present in this batch before
        # processing replies. This makes reply resolution a local SQLite lookup.
        for item in unread:
            if _DEDICATED_WORKFLOW_KEYS.intersection(item.flags):
                self.relations.ensure_workflow_focus(item.email.message_id)
        self._progress(
            phase="triage",
            label="TriageBox: 新着・WIB依頼確認",
            current=0,
            total=len(unread),
            errors=0,
        )
        logging.info(
            "TriageBox will process %d new/support-request candidate messages oldest-first",
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
            self._progress(
                phase="triage-relations",
                label="TriageBox: 返信関係確認",
                current=index,
                total=len(unread),
                errors=len(errors),
            )
            try:
                # The extension-controlled origin header is a stronger signal
                # than the From address. Thunderbird may send through an
                # identity/alias that is not listed in config.identity, but the
                # self-Cc copy is still the WIB support request M2.
                if item.headers.origin_message_id is not None:
                    if self._handle_self_support_request(item):
                        support_requests += 1
                elif kind == TriageSenderKind.SELF:
                    logging.info("TriageBox self mail: no origin header; no transition")
                elif self._handle_waiting_action_reply(item):
                    waiting_action_replies += 1
                else:
                    self._handle_dedicated_thread_focus(item)
            except (OSError, RuntimeError, ValueError) as exc:
                logging.warning(
                    "TriageBox failed for %s: %s",
                    item.email.message_id,
                    exc,
                )
                errors.append(self._error(item, exc))
            self._progress(
                phase="triage",
                label="TriageBox: 新着・WIB依頼確認",
                current=index,
                total=len(unread),
                errors=len(errors),
            )

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
        relation_kind = self.relations.relation_kind_for(item.email.message_id)
        if relation_kind == _SUPPORT_REQUEST_REPLIED:
            logging.info("TriageBox self mail: support request already replied; no reactivation")
            return False
        if (
            relation_kind == _SUPPORT_REQUEST
            and _WAITING_ACTION in item.flags
            and "\\Flagged" in item.flags
        ):
            logging.info("TriageBox self mail: support request already active; no transition")
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

        self.relations.ensure_workflow_focus(origin_message_id)
        self._set_keyword(item, _WAITING_ACTION, enabled=True)
        self._set_flagged(item, enabled=True)
        self.relations.record(
            item.email.message_id,
            origin_message_id,
            _SUPPORT_REQUEST,
        )
        logging.info(
            "TriageBox self mail: support request marked waiting-action/starred and relation saved: %s",
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
            self.relations.ensure_workflow_focus(origin_message_id)
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

    def _handle_dedicated_thread_focus(self, item: TriageMessage) -> bool:
        referenced_message_ids = item.headers.referenced_message_ids

        # Resolve every reference against the local relation store first.  This is
        # inexpensive and covers continuations of workflows already known to WIB.
        for message_id in referenced_message_ids:
            relation_kind = self.relations.relation_kind_for(message_id)
            if relation_kind in _SUPPORT_RELATION_KINDS:
                continue

            workflow_origin = self.relations.workflow_origin_for_focus(message_id)
            if workflow_origin is not None:
                return self._move_dedicated_thread_focus(
                    item, workflow_origin=workflow_origin
                )

        # Do not search the whole mailbox for unknown references. Dedicated
        # origins are registered when their WIB tag is assigned (or when such a
        # message is present in this unread batch), so an unknown reference is an
        # ordinary mail thread from TriageBox's point of view.
        return False

    def _move_dedicated_thread_focus(
        self,
        item: TriageMessage,
        *,
        workflow_origin: str,
    ) -> bool:
        previous_focus = self.relations.current_focus_for(workflow_origin)
        if previous_focus == item.email.message_id:
            return True

        if previous_focus and previous_focus != workflow_origin:
            previous = self.imap_client.find_message_by_message_id(previous_focus)
            if previous is not None:
                self._set_keyword(previous, _BULK, enabled=True)
                self._set_flagged(previous, enabled=False)

        self._set_flagged(item, enabled=True)
        self.relations.set_current_focus(workflow_origin, item.email.message_id)
        logging.info(
            "TriageBox dedicated thread focus moved: origin=%s previous=%s current=%s",
            workflow_origin,
            previous_focus or "<none>",
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
