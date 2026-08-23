from __future__ import annotations

import imaplib
from dataclasses import dataclass
from datetime import date, timedelta

from .config import AppConfig
from .database import EmailDatabase
from .record_store import RecordStore


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    unattended_lookback_days: int
    unattended_unread: int
    unattended_read: int
    answer: int
    review: int
    watch: int
    deadline: int
    schedule: int
    pending: int
    waiting_reply: int
    waiting_action: int
    action_ready: int
    records: int

    @property
    def normal_total(self) -> int:
        return self.answer + self.review + self.watch

    @property
    def dedicated_total(self) -> int:
        return self.deadline + self.schedule

    @property
    def waiting_total(self) -> int:
        return self.waiting_reply + self.waiting_action + self.action_ready


class DashboardService:
    def __init__(
        self,
        config: AppConfig,
        *,
        record_store: RecordStore | None = None,
        database: EmailDatabase | None = None,
    ) -> None:
        self.config = config
        self.records = record_store or RecordStore(config.database.path)
        self.database = database or EmailDatabase(config.database.path)

    def snapshot(self) -> DashboardSnapshot:
        self.records.initialize()
        self.database.initialize()
        active_uids = {
            reference.uid
            for reference in self.database.active_imap_references(
                self.config.imap.mailbox
            )
        }
        unattended_since = date.today() - timedelta(
            days=self.config.imap.new_mail_lookback_days - 1
        )
        unattended_since_text = unattended_since.strftime("%d-%b-%Y")

        with imaplib.IMAP4_SSL(
            self.config.imap.host,
            self.config.imap.port,
            timeout=self.config.imap.timeout_seconds,
        ) as client:
            client.login(self.config.imap.username, self.config.imap.password)
            status, _ = client.select(self.config.imap.mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Unable to select mailbox: {self.config.imap.mailbox}")

            unattended_unread = self._count(
                client,
                "UNSEEN",
                "UNFLAGGED",
                "UNKEYWORD",
                "wib-bulk",
                "UNKEYWORD",
                "wib-batch",
                "SINCE",
                unattended_since_text,
            )
            unattended_read = self._count(
                client,
                "SEEN",
                "UNFLAGGED",
                "UNKEYWORD",
                "wib-bulk",
                "UNKEYWORD",
                "wib-batch",
                "SINCE",
                unattended_since_text,
            )

            return DashboardSnapshot(
                unattended_lookback_days=self.config.imap.new_mail_lookback_days,
                unattended_unread=unattended_unread,
                unattended_read=unattended_read,
                answer=self._count(client, "FLAGGED", "KEYWORD", "wib-answer"),
                review=self._count(client, "FLAGGED", "KEYWORD", "wib-review"),
                watch=self._count(client, "FLAGGED", "KEYWORD", "wib-watch"),
                deadline=self._count(
                    client,
                    "FLAGGED",
                    "KEYWORD",
                    "wib-deadline",
                    "UNKEYWORD",
                    "wib-deadline-done",
                    allowed_uids=active_uids,
                ),
                schedule=self._count(
                    client,
                    "FLAGGED",
                    "KEYWORD",
                    "wib-schedule",
                    "UNKEYWORD",
                    "wib-schedule-done",
                    allowed_uids=active_uids,
                ),
                pending=self._count(client, "FLAGGED", "KEYWORD", "wib-pending"),
                waiting_reply=self._count(
                    client, "FLAGGED", "KEYWORD", "wib-waiting-reply"
                ),
                waiting_action=self._count(
                    client, "FLAGGED", "KEYWORD", "wib-waiting-action"
                ),
                action_ready=self._count(
                    client, "FLAGGED", "KEYWORD", "wib-action-ready"
                ),
                records=len(self.records.list()),
            )

    @staticmethod
    def _count(
        client: imaplib.IMAP4_SSL,
        *criteria: str,
        allowed_uids: set[int] | None = None,
    ) -> int:
        if allowed_uids is None:
            status, data = client.search(None, *criteria)
        else:
            status, data = client.uid("search", None, *criteria)
        if status != "OK":
            raise RuntimeError(f"IMAP dashboard search failed: {' '.join(criteria)}")
        values = data[0].split() if data and data[0] else []
        if allowed_uids is None:
            return len(values)
        return sum(int(value) in allowed_uids for value in values)
