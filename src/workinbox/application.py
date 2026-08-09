from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .config import AppConfig
from .database import EmailDatabase
from .imap_client import ImapClient
from .models import ImapCheckState, TrackedEmail, TrackingStatus
from .work_tags import WorkTagDefinition, definitions_for_flags, require_work_tag


class SyncMode(StrEnum):
    NORMAL = "normal"
    FULL_RECHECK = "full_recheck"


@dataclass(frozen=True, slots=True)
class SyncError:
    message_id: str
    message: str


@dataclass(frozen=True, slots=True)
class SyncResult:
    mode: SyncMode
    checked: int
    flagged: int
    added: int
    reactivated: int
    inactivated: int
    errors: tuple[SyncError, ...]


@dataclass(frozen=True, slots=True)
class TrackedEmailTagView:
    email: TrackedEmail
    tags: tuple[WorkTagDefinition, ...]
    error: str | None = None


class SynchronizationService:
    def __init__(
        self,
        config: AppConfig,
        *,
        database: EmailDatabase | None = None,
        imap_client: ImapClient | None = None,
    ) -> None:
        self.config = config
        self.database = database or EmailDatabase(config.database.path)
        self.imap_client = imap_client or ImapClient(config.imap)

    def synchronize(self, mode: SyncMode = SyncMode.NORMAL) -> SyncResult:
        self.database.initialize()
        include_inactive = mode == SyncMode.FULL_RECHECK
        existing = self.database.imap_references(
            self.config.imap.mailbox,
            include_inactive=include_inactive,
        )

        checks, messages = self.imap_client.synchronize(existing)
        inactivated = 0
        reactivated_from_checks = 0
        errors: list[SyncError] = []

        for check in checks:
            if check.state == ImapCheckState.ERROR:
                errors.append(
                    SyncError(
                        message_id=check.message_id,
                        message=check.error or "unknown IMAP error",
                    )
                )
                continue

            target = {
                ImapCheckState.FLAGGED: TrackingStatus.ACTIVE,
                ImapCheckState.UNSTARRED: TrackingStatus.INACTIVE_UNSTARRED,
                ImapCheckState.MISSING: TrackingStatus.INACTIVE_MOVED,
            }[check.state]
            changed = self.database.update_tracking_status(check.message_id, target)
            if not changed:
                continue
            if target == TrackingStatus.ACTIVE:
                reactivated_from_checks += 1
            else:
                inactivated += 1

        added, reactivated_from_discovery = self.database.synchronize(messages)
        return SyncResult(
            mode=mode,
            checked=len(checks),
            flagged=len(messages),
            added=added,
            reactivated=reactivated_from_checks + reactivated_from_discovery,
            inactivated=inactivated,
            errors=tuple(errors),
        )

    def normal_sync(self) -> SyncResult:
        return self.synchronize(SyncMode.NORMAL)

    def full_recheck(self) -> SyncResult:
        return self.synchronize(SyncMode.FULL_RECHECK)


class TrackingQueryService:
    def __init__(
        self,
        config: AppConfig,
        *,
        database: EmailDatabase | None = None,
    ) -> None:
        self.config = config
        self.database = database or EmailDatabase(config.database.path)

    def active_emails(self) -> list[TrackedEmail]:
        self.database.initialize()
        return self.database.list_tracked_emails(active=True)

    def inactive_emails(self) -> list[TrackedEmail]:
        self.database.initialize()
        return self.database.list_tracked_emails(active=False)


class WorkTagService:
    def __init__(
        self,
        config: AppConfig,
        *,
        database: EmailDatabase | None = None,
        imap_client: ImapClient | None = None,
    ) -> None:
        self.config = config
        self.database = database or EmailDatabase(config.database.path)
        self.imap_client = imap_client or ImapClient(config.imap)

    def read_for_emails(self, emails: list[TrackedEmail]) -> list[TrackedEmailTagView]:
        views: list[TrackedEmailTagView] = []
        for email in emails:
            if email.uid is None or email.uidvalidity is None or email.mailbox is None:
                views.append(
                    TrackedEmailTagView(
                        email=email,
                        tags=(),
                        error="IMAP identity is unavailable",
                    )
                )
                continue
            if email.mailbox != self.config.imap.mailbox:
                views.append(
                    TrackedEmailTagView(
                        email=email,
                        tags=(),
                        error=f"mailbox mismatch: {email.mailbox}",
                    )
                )
                continue
            try:
                snapshot = self.imap_client.inspect_flags(
                    email.uid,
                    expected_uidvalidity=email.uidvalidity,
                )
            except (OSError, RuntimeError) as exc:
                views.append(TrackedEmailTagView(email=email, tags=(), error=str(exc)))
                continue
            views.append(
                TrackedEmailTagView(
                    email=email,
                    tags=definitions_for_flags(snapshot.flags),
                )
            )
        return views

    def set_tag(self, message_id: str, key: str, *, enabled: bool) -> None:
        tag = require_work_tag(key)
        self.database.initialize()
        reference = self.database.imap_reference(message_id)
        if reference is None:
            raise RuntimeError(f"IMAP identity is unavailable for {message_id}")
        if reference.mailbox != self.config.imap.mailbox:
            raise RuntimeError(
                f"Mail is stored in {reference.mailbox!r}, not configured mailbox "
                f"{self.config.imap.mailbox!r}"
            )
        self.imap_client.set_keyword(
            reference.uid,
            tag.key,
            enabled=enabled,
            expected_uidvalidity=reference.uidvalidity,
        )
