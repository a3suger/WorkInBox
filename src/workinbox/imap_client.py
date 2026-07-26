from __future__ import annotations

import imaplib
from email import message_from_bytes, policy
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses

from .config import ImapConfig
from .models import EmailMessage


def _decode_header(value: str | None) -> str | None:
    if value is None:
        return None
    return str(make_header(decode_header(value)))


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


class ImapClient:
    def __init__(self, config: ImapConfig) -> None:
        self.config = config

    def fetch_flagged(self) -> list[EmailMessage]:
        messages: list[EmailMessage] = []
        with imaplib.IMAP4_SSL(self.config.host, self.config.port) as client:
            client.login(self.config.username, self.config.password)
            status, _ = client.select(self.config.mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Unable to select mailbox: {self.config.mailbox}")

            status, data = client.uid("search", None, "FLAGGED")
            if status != "OK":
                raise RuntimeError("IMAP FLAGGED search failed")

            for uid in data[0].split() if data and data[0] else []:
                status, fetched = client.uid("fetch", uid, "(BODY.PEEK[])")
                if status != "OK":
                    raise RuntimeError(f"IMAP fetch failed for UID {uid.decode()}")
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
                    )
                )
        return messages
