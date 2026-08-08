from __future__ import annotations

import imaplib
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


_FLAGGED_RE = re.compile(rb"(?:^|[ (])\\Flagged(?:[ )]|$)", re.IGNORECASE)
_FLAGS_RE = re.compile(rb"FLAGS \(([^)]*)\)", re.IGNORECASE)


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


def _new_mail_since(today: date, lookback_days: int) -> date:
    return today - timedelta(days=lookback_days - 1)


class ImapClient:
    def __init__(self, config: ImapConfig) -> None:
        self.config = config

    def inspect_flags(self, uid: int) -> ImapFlagsSnapshot:
        with imaplib.IMAP4_SSL(self.config.host, self.config.port) as client:
            client.login(self.config.username, self.config.password)
            status, _ = client.select(self.config.mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Unable to select mailbox: {self.config.mailbox}")

            current_uidvalidity = _uidvalidity(client)
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
                raw = next(
                    (item[1] for item in fetched if isinstance(item, tuple)),
                    None,
                )
                if not isinstance(raw, bytes):
                    continue
                parsed = message_from_bytes(raw, policy=policy.default)
                message_id = (parsed.get("Message-ID") or "").strip()
                if not message_id:
                    continue
                messages.append(
                    EmailMessage(
                        message_id=message_id,
                        sender=_addresses(parsed, "From") or "",
                        recipients=_addresses(parsed, "To"),
                        subject=_decode_header(parsed.get("Subject")),
                        received_at=parsed.get("Date"),
                        body=_body(parsed),
                        mailbox=self.config.mailbox,
                        uidvalidity=current_uidvalidity,
                        uid=uid,
                    )
                )
        return checks, messages

    def fetch_flagged(self) -> list[EmailMessage]:
        _, messages = self.synchronize(())
        return messages
