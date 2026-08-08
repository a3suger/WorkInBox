from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .config import AppConfig
from .database import EmailDatabase
from .imap_client import ImapClient
from .models import ImapCheckState, TrackingStatus


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
            if changed and target != TrackingStatus.ACTIVE:
                inactivated += 1

        added, reactivated = self.database.synchronize(messages)
        return SyncResult(
            mode=mode,
            checked=len(checks),
            flagged=len(messages),
            added=added,
            reactivated=reactivated,
            inactivated=inactivated,
            errors=tuple(errors),
        )

    def normal_sync(self) -> SyncResult:
        return self.synchronize(SyncMode.NORMAL)

    def full_recheck(self) -> SyncResult:
        return self.synchronize(SyncMode.FULL_RECHECK)
