from __future__ import annotations

import imaplib
import logging
import re
from collections.abc import Iterable
from datetime import date, timedelta
from email import message_from_bytes, policy
from email.header import decode_header
from email.message import Message
from email.utils import getaddresses

from .config import ImapConfig
from .models import (
    EmailMessage,
    ImapCheckResult,
    ImapCheckState,
    ImapFlagsSnapshot,
    ImapReference,
)
from .triagebox import TriageMessage, parse_triage_headers


_FLAGGED_RE = re.compile(rb"(?:^|[ (])\\Flagged(?:[ )]|$)", re.IGNORECASE)
_FLAGS_RE = re.compile(rb"FLAGS \(([^)]*)\)", re.IGNORECASE)
_INTERNALDATE_RE = re.compile(rb'INTERNALDATE "([^"]+)"', re.IGNORECASE)
_KEYWORD_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _decode_header(value: str | None) -> str | None:
    if value is None:
        return None

    decoded_parts: list[str] = []
    for part, charset in decode_header(str(value)):
        if isinstance(part, str):
            decoded_parts.append(part)
            continue

        encoding = charset or "utf-8"
        try:
            decoded_parts.append(part.decode(encoding, errors="replace"))
        except LookupError:
            decoded_parts.append(part.decode("utf-8", errors="replace"))

    return "".join(decoded_parts)


def _addresses(message: Message, header: str) -> str | None:
    values = message.get_all(header, [])
    addresses = [address for _, address in getaddresses(values) if address]
    return ", ".join(addresses) or None


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _body(message: Message) -> str | None:
    if not message.is_multipart():
        return _decode_part(message)

    plain: list[str] = []
    html: list[str] = []
    for part in message.walk():
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type == "text/plain":
            plain.append(_decode_part(part))
        elif content_type == "text/html":
            html.append(_decode_part(part))
    selected = plain or html
    return "\n".join(selected) if selected else None


def _uidvalidity(client: imaplib.IMAP4_SSL) -> int:
    status, data = client.response("UIDVALIDITY")
    if status != "UIDVALIDITY" or not data or data[0] is None:
        raise RuntimeError("IMAP UIDVALIDITY is unavailable")
    try:
        return int(data[0])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid IMAP UIDVALIDITY response") from exc


def _fetch_has_flagged(fetched: list[bytes | tuple[bytes, bytes] | None]) -> bool | None:
    metadata = [
        item[0] if isinstance(item, tuple) else item
        for item in fetched
        if item is not None
    ]
    if not metadata:
        return None
    return any(isinstance(item, bytes) and _FLAGGED_RE.search(item) for item in metadata)


def _parse_flags(fetched: list[bytes | tuple[bytes, bytes] | None]) -> tuple[str, ...]:
    for item in fetched:
        metadata = item[0] if isinstance(item, tuple) else item
        if not isinstance(metadata, bytes):
            continue
        match = _FLAGS_RE.search(metadata)
        if match is None:
            continue
        raw_flags = match.group(1).decode("utf-8", errors="replace").strip()
        return tuple(raw_flags.split()) if raw_flags else ()
    raise RuntimeError("IMAP FLAGS are unavailable for the requested UID")


def _parse_internaldate(fetched: list[bytes | tuple[bytes, bytes] | None]) -> str | None:
    for item in fetched:
        metadata = item[0] if isinstance(item, tuple) else item
        if not isinstance(metadata, bytes):
            continue
        match = _INTERNALDATE_RE.search(metadata)
        if match is not None:
            return match.group(1).decode("ascii", errors="replace")
    return None


def _validate_keyword(keyword: str) -> None:
    if not _KEYWORD_RE.fullmatch(keyword):
        raise ValueError(f"Invalid IMAP keyword: {keyword!r}")


def _new_mail_since(today: date, lookback_days: int) -> date:
    return today - timedelta(days=lookback_days - 1)


def _email_message(parsed: Message, mailbox: str, uidvalidity: int, uid: int) -> EmailMessage | None:
    message_id = (parsed.get("Message-ID") or "").strip()
    if not message_id:
        return None
    return EmailMessage(
        message_id=message_id,
        sender=_addresses(parsed, "From") or "",
        recipients=_addresses(parsed, "To"),
        subject=_decode_header(parsed.get("Subject")),
        received_at=parsed.get("Date"),
        body=_body(parsed),
        mailbox=mailbox,
        uidvalidity=uidvalidity,
        uid=uid,
    )


def _raw_from_fetch(fetched: list[bytes | tuple[bytes, bytes] | None]) -> bytes | None:
    return next((item[1] for item in fetched if isinstance(item, tuple)), None)


class ImapClient:
    def __init__(self, config: ImapConfig) -> None:
        self.config = config

    def inspect_flags(self, uid: int, *, expected_uidvalidity: int | None = None) -> ImapFlagsSnapshot:
        with imaplib.IMAP4_SSL(self.config.host, self.config.port) as client:
            client.login(self.config.username, self.config.password)
            status, _ = client.select(self.config.mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Unable to select mailbox: {self.config.mailbox}")

            current_uidvalidity = _uidvalidity(client)
            if expected_uidvalidity is not None and current_uidvalidity != expected_uidvalidity:
                raise RuntimeError("IMAP UIDVALIDITY changed; tag operation aborted")
            status, fetched = client.uid("fetch", str(uid), "(UID FLAGS)")
            if status != "OK":
                raise RuntimeError(f"IMAP fetch failed for UID {uid}")
            flags = _parse_flags(fetched)
            return ImapFlagsSnapshot(
                mailbox=self.config.mailbox,
                uidvalidity=current_uidvalidity,
                uid=uid,
                flags=flags,
            )

    def set_keyword(
        self,
        uid: int,
        keyword: str,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        return self.set_keywords(
            uid,
            (keyword,),
            enabled=enabled,
            expected_uidvalidity=expected_uidvalidity,
        )

    def set_keywords(
        self,
        uid: int,
        keywords: Iterable[str],
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        unique_keywords = tuple(dict.fromkeys(keywords))
        if not unique_keywords:
            raise ValueError("At least one IMAP keyword is required")
        for keyword in unique_keywords:
            _validate_keyword(keyword)
        operation = "+FLAGS.SILENT" if enabled else "-FLAGS.SILENT"
        keyword_list = " ".join(unique_keywords)
        return self._store_flags(
            uid,
            operation,
            f"({keyword_list})",
            expected_uidvalidity=expected_uidvalidity,
        )

    def set_flagged(
        self,
        uid: int,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        operation = "+FLAGS.SILENT" if enabled else "-FLAGS.SILENT"
        return self._store_flags(
            uid,
            operation,
            "(\\Flagged)",
            expected_uidvalidity=expected_uidvalidity,
        )

    def _store_flags(
        self,
        uid: int,
        operation: str,
        flags: str,
        *,
        expected_uidvalidity: int | None,
    ) -> ImapFlagsSnapshot:
        with imaplib.IMAP4_SSL(self.config.host, self.config.port) as client:
            client.login(self.config.username, self.config.password)
            status, _ = client.select(self.config.mailbox, readonly=False)
            if status != "OK":
                raise RuntimeError(f"Unable to select mailbox: {self.config.mailbox}")

            current_uidvalidity = _uidvalidity(client)
            if expected_uidvalidity is not None and current_uidvalidity != expected_uidvalidity:
                raise RuntimeError("IMAP UIDVALIDITY changed; tag operation aborted")
            status, _ = client.uid("store", str(uid), operation, flags)
            if status != "OK":
                raise RuntimeError(f"Unable to update IMAP flags {flags!r} for UID {uid}")

            status, fetched = client.uid("fetch", str(uid), "(UID FLAGS)")
            if status != "OK":
                raise RuntimeError(f"IMAP fetch failed for UID {uid} after flag update")
            return ImapFlagsSnapshot(
                mailbox=self.config.mailbox,
                uidvalidity=current_uidvalidity,
                uid=uid,
                flags=_parse_flags(fetched),
            )

    def fetch_unread(self) -> list[TriageMessage]:
        with imaplib.IMAP4_SSL(self.config.host, self.config.port) as client:
            client.login(self.config.username, self.config.password)
            status, _ = client.select(self.config.mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Unable to select mailbox: {self.config.mailbox}")
            current_uidvalidity = _uidvalidity(client)
            since = _new_mail_since(date.today(), self.config.new_mail_lookback_days)
            since_text = since.strftime("%d-%b-%Y")
            logging.info(
                "TriageBox IMAP search: UNSEEN SINCE %s (lookback_days=%d)",
                since_text,
                self.config.new_mail_lookback_days,
            )
            status, data = client.uid("search", None, "UNSEEN", "SINCE", since_text)
            if status != "OK":
                raise RuntimeError("IMAP UNSEEN search failed")
            uid_values = data[0].split() if data and data[0] else []
            logging.info("TriageBox IMAP search returned %d candidate UIDs", len(uid_values))

            ordered: list[tuple[str, int, TriageMessage]] = []
            for index, uid_bytes in enumerate(uid_values, start=1):
                uid = int(uid_bytes)
                logging.info(
                    "TriageBox IMAP fetch %d/%d: uid=%d",
                    index,
                    len(uid_values),
                    uid,
                )
                item, internaldate = self._fetch_triage_message(
                    client,
                    uid,
                    current_uidvalidity,
                    include_internaldate=True,
                )
                if item is not None:
                    # INTERNALDATE is an IMAP server arrival timestamp. Its
                    # wire representation sorts correctly after normalizing to
                    # the parsed datetime tuple through Internaldate2tuple.
                    metadata = f'INTERNALDATE "{internaldate}"'.encode() if internaldate else b""
                    parsed_date = imaplib.Internaldate2tuple(metadata) if internaldate else None
                    sort_key = (
                        "%04d%02d%02d%02d%02d%02d"
                        % parsed_date[:6]
                        if parsed_date is not None
                        else "99999999999999"
                    )
                    ordered.append((sort_key, uid, item))
                    logging.info(
                        "TriageBox IMAP candidate ready: uid=%d internaldate=%s message_id=%s",
                        uid,
                        internaldate or "<unavailable>",
                        item.email.message_id,
                    )

            ordered.sort(key=lambda value: (value[0], value[1]))
            logging.info("TriageBox IMAP candidates sorted oldest-first")
            return [item for _, _, item in ordered]

    def find_message_by_message_id(self, message_id: str) -> TriageMessage | None:
        with imaplib.IMAP4_SSL(self.config.host, self.config.port) as client:
            client.login(self.config.username, self.config.password)
            status, _ = client.select(self.config.mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Unable to select mailbox: {self.config.mailbox}")
            current_uidvalidity = _uidvalidity(client)
            status, data = client.uid("search", None, "HEADER", "Message-ID", message_id)
            if status != "OK":
                raise RuntimeError(f"IMAP Message-ID search failed for {message_id}")
            uid_values = data[0].split() if data and data[0] else []
            for uid_bytes in reversed(uid_values):
                item, _ = self._fetch_triage_message(client, int(uid_bytes), current_uidvalidity)
                if item is not None:
                    return item
            return None

    def _fetch_triage_message(
        self,
        client: imaplib.IMAP4_SSL,
        uid: int,
        current_uidvalidity: int,
        *,
        include_internaldate: bool = False,
    ) -> tuple[TriageMessage | None, str | None]:
        query = "(UID FLAGS INTERNALDATE BODY.PEEK[])" if include_internaldate else "(UID FLAGS BODY.PEEK[])"
        status, fetched = client.uid("fetch", str(uid), query)
        if status != "OK":
            return None, None
        raw = _raw_from_fetch(fetched)
        if not isinstance(raw, bytes):
            return None, None
        parsed = message_from_bytes(raw, policy=policy.default)
        email = _email_message(parsed, self.config.mailbox, current_uidvalidity, uid)
        if email is None:
            return None, None
        return (
            TriageMessage(
                email=email,
                headers=parse_triage_headers(parsed),
                flags=_parse_flags(fetched),
            ),
            _parse_internaldate(fetched) if include_internaldate else None,
        )

    def synchronize(
        self,
        existing: Iterable[ImapReference],
    ) -> tuple[list[ImapCheckResult], list[EmailMessage]]:
        checks: list[ImapCheckResult] = []
        messages: list[EmailMessage] = []
        with imaplib.IMAP4_SSL(self.config.host, self.config.port) as client:
            client.login(self.config.username, self.config.password)
            status, _ = client.select(self.config.mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Unable to select mailbox: {self.config.mailbox}")

            current_uidvalidity = _uidvalidity(client)
            for reference in existing:
                if reference.uidvalidity != current_uidvalidity:
                    raise RuntimeError(
                        "IMAP UIDVALIDITY changed; automatic recovery is not supported"
                    )
                try:
                    status, fetched = client.uid(
                        "fetch", str(reference.uid), "(UID FLAGS)"
                    )
                except (imaplib.IMAP4.error, OSError) as exc:
                    checks.append(
                        ImapCheckResult(
                            reference.message_id,
                            ImapCheckState.ERROR,
                            str(exc),
                        )
                    )
                    continue
                if status != "OK":
                    checks.append(
                        ImapCheckResult(
                            reference.message_id,
                            ImapCheckState.ERROR,
                            f"IMAP fetch failed for UID {reference.uid}",
                        )
                    )
                    continue
                flagged = _fetch_has_flagged(fetched)
                if flagged is None:
                    checks.append(
                        ImapCheckResult(reference.message_id, ImapCheckState.MISSING)
                    )
                elif flagged:
                    checks.append(
                        ImapCheckResult(reference.message_id, ImapCheckState.FLAGGED)
                    )
                else:
                    checks.append(
                        ImapCheckResult(reference.message_id, ImapCheckState.UNSTARRED)
                    )

            since = _new_mail_since(date.today(), self.config.new_mail_lookback_days)
            status, data = client.uid(
                "search", None, "FLAGGED", "SINCE", since.strftime("%d-%b-%Y")
            )
            if status != "OK":
                raise RuntimeError("IMAP FLAGGED search failed")

            for uid_bytes in data[0].split() if data and data[0] else []:
                uid = int(uid_bytes)
                try:
                    status, fetched = client.uid(
                        "fetch", uid_bytes, "(UID BODY.PEEK[])"
                    )
                except (imaplib.IMAP4.error, OSError):
                    continue
                if status != "OK":
                    continue
                raw = _raw_from_fetch(fetched)
                if not isinstance(raw, bytes):
                    continue
                parsed = message_from_bytes(raw, policy=policy.default)
                message = _email_message(parsed, self.config.mailbox, current_uidvalidity, uid)
                if message is not None:
                    messages.append(message)
        return checks, messages

    def fetch_flagged(self) -> list[EmailMessage]:
        _, messages = self.synchronize(())
        return messages
