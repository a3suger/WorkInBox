from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter

from .ai_classifier import OllamaClassifier
from .config import AppConfig
from .database import EmailDatabase
from .deadline_dates import normalize_due_at
from .imap_client import ImapClient
from .models import (
    Deadline,
    DeadlineCandidate,
    DeadlineCreatedBy,
    ImapCheckState,
    ImapFlagsSnapshot,
    ImapReference,
    TrackedEmail,
    TrackingStatus,
)
from .triage_store import TriageRelationStore
from .triagebox import TriageResult, TriageService
from .sync_progress import ProgressCallback
from .work_tags import WorkTagDefinition, definitions_for_flags, require_work_tag


_INITIAL_CLASSIFICATION_KEYS = frozenset(
    {
        "wib-deadline",
        "wib-schedule",
        "wib-answer",
        "wib-review",
        "wib-watch",
        "wib-pending",
        "wib-bulk",
    }
)
_TRIAGE_MANAGED_KEYS = frozenset(
    {"wib-waiting-reply", "wib-waiting-action", "wib-action-ready"}
)
_NORMAL_RESOLUTION_KEYS = frozenset(
    {"wib-answer", "wib-review", "wib-watch", "wib-pending", "wib-bulk"}
)

_PENDING_RESOLUTIONS: dict[str, tuple[str, ...]] = {
    "answer": ("wib-answer",),
    "review": ("wib-review",),
    "watch": ("wib-watch",),
    "none": ("wib-bulk",),
}


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
    ai_classified: int = 0
    ai_errors: tuple[SyncError, ...] = ()
    triage_scanned: int = 0
    triage_support_requests: int = 0
    triage_waiting_action_replies: int = 0
    triage_errors: tuple[SyncError, ...] = ()


@dataclass(frozen=True, slots=True)
class TrackedEmailTagView:
    email: TrackedEmail
    tags: tuple[WorkTagDefinition, ...]
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PendingEmailView:
    email: TrackedEmail
    tags: tuple[WorkTagDefinition, ...]
    body: str | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class _AiClassificationOutcome:
    message_id: str
    classified: bool
    error: str | None = None


class SynchronizationService:
    def __init__(
        self,
        config: AppConfig,
        *,
        database: EmailDatabase | None = None,
        imap_client: ImapClient | None = None,
        classifier: OllamaClassifier | None = None,
        triage_service: TriageService | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.config = config
        self.database = database or EmailDatabase(config.database.path)
        self.progress_callback = progress_callback
        self.imap_client = imap_client or ImapClient(
            config.imap,
            progress_callback=progress_callback,
        )
        self.classifier = classifier or OllamaClassifier(config.ai)
        self.triage_service = triage_service or TriageService(
            config,
            self.imap_client,
            progress_callback=progress_callback,
        )

    def _progress(self, **event: object) -> None:
        if self.progress_callback is not None:
            self.progress_callback(dict(event))

    def synchronize(self, mode: SyncMode = SyncMode.NORMAL) -> SyncResult:
        self.database.initialize()

        self._progress(phase="starting", label="同期準備", current=0, total=None, errors=0)

        triage_result = TriageResult()
        if mode == SyncMode.NORMAL:
            triage_result = self.triage_service.run()

        include_inactive = mode == SyncMode.FULL_RECHECK
        existing = self.database.imap_references(
            self.config.imap.mailbox,
            include_inactive=include_inactive,
        )

        self._progress(
            phase="tracking",
            label="TrackingBox: 既存active確認と新着取り込み",
            current=0,
            total=len(existing),
            errors=0,
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
        ai_classified = 0
        ai_errors: tuple[SyncError, ...] = ()
        if mode == SyncMode.NORMAL:
            ai_classified, ai_errors = self._classify_unclassified_active()

        self._progress(
            phase="complete",
            label="同期完了",
            current=1,
            total=1,
            errors=len(triage_result.errors) + len(errors) + len(ai_errors),
        )

        return SyncResult(
            mode=mode,
            checked=len(checks),
            flagged=len(messages),
            added=added,
            reactivated=reactivated_from_checks + reactivated_from_discovery,
            inactivated=inactivated,
            errors=tuple(errors),
            ai_classified=ai_classified,
            ai_errors=ai_errors,
            triage_scanned=triage_result.scanned,
            triage_support_requests=triage_result.support_requests,
            triage_waiting_action_replies=triage_result.waiting_action_replies,
            triage_errors=tuple(
                SyncError(error.message_id, error.message)
                for error in triage_result.errors
            ),
        )

    def _eligible_unclassified(
        self,
    ) -> tuple[list[TrackedEmail], list[SyncError]]:
        eligible: list[TrackedEmail] = []
        errors: list[SyncError] = []
        tracked_emails = self.database.list_tracked_emails(active=True)
        self._progress(
            phase="tracking-ai-check",
            label="TrackingBox: AI分類対象確認",
            current=0,
            total=len(tracked_emails),
            errors=0,
        )
        for current, tracked in enumerate(tracked_emails, start=1):
            if tracked.uid is None or tracked.uidvalidity is None or tracked.mailbox is None:
                self._progress(
                    phase="tracking-ai-check",
                    label="TrackingBox: AI分類対象確認",
                    current=current,
                    total=len(tracked_emails),
                    errors=len(errors),
                )
                continue
            if tracked.mailbox != self.config.imap.mailbox:
                self._progress(
                    phase="tracking-ai-check",
                    label="TrackingBox: AI分類対象確認",
                    current=current,
                    total=len(tracked_emails),
                    errors=len(errors),
                )
                continue
            try:
                snapshot = self.imap_client.inspect_flags(
                    tracked.uid,
                    expected_uidvalidity=tracked.uidvalidity,
                )
            except (OSError, RuntimeError, ValueError) as exc:
                logging.warning(
                    "AI precheck failed for %s: %s",
                    tracked.message_id,
                    exc,
                )
                errors.append(SyncError(tracked.message_id, str(exc)))
                self._progress(
                    phase="tracking-ai-check",
                    label="TrackingBox: AI分類対象確認",
                    current=current,
                    total=len(tracked_emails),
                    errors=len(errors),
                )
                continue
            if (_INITIAL_CLASSIFICATION_KEYS | _TRIAGE_MANAGED_KEYS).intersection(snapshot.flags):
                self._progress(
                    phase="tracking-ai-check",
                    label="TrackingBox: AI分類対象確認",
                    current=current,
                    total=len(tracked_emails),
                    errors=len(errors),
                )
                continue
            eligible.append(tracked)
            self._progress(
                phase="tracking-ai-check",
                label="TrackingBox: AI分類対象確認",
                current=current,
                total=len(tracked_emails),
                errors=len(errors),
            )
        return eligible, errors

    def _classify_one(self, tracked: TrackedEmail) -> _AiClassificationOutcome:
        started = perf_counter()
        try:
            message = self.database.email_message(tracked.message_id)
            if message is None:
                raise RuntimeError("email content is unavailable in SQLite")
            classification = self.classifier.classify(message)
            tag_keys = classification.tag_keys()
            self.imap_client.set_keywords(
                tracked.uid,
                tag_keys,
                enabled=True,
                expected_uidvalidity=tracked.uidvalidity,
            )
            if {"wib-schedule", "wib-deadline"}.intersection(tag_keys):
                relation_store = TriageRelationStore(self.config.database.path)
                relation_store.initialize()
                relation_store.ensure_workflow_focus(tracked.message_id)
            if classification.should_unstar():
                try:
                    self.imap_client.set_flagged(
                        tracked.uid,
                        enabled=False,
                        expected_uidvalidity=tracked.uidvalidity,
                    )
                except (OSError, RuntimeError, ValueError):
                    try:
                        self.imap_client.set_keywords(
                            tracked.uid,
                            tag_keys,
                            enabled=False,
                            expected_uidvalidity=tracked.uidvalidity,
                        )
                    except (OSError, RuntimeError, ValueError):
                        logging.exception(
                            "Failed to roll back AI bulk tag for %s",
                            tracked.message_id,
                        )
                    raise
                self.database.update_tracking_status(
                    tracked.message_id,
                    TrackingStatus.INACTIVE_UNSTARRED,
                )
        except (OSError, RuntimeError, ValueError) as exc:
            elapsed = perf_counter() - started
            logging.warning(
                "AI classification failed for %s after %.2fs: %s",
                tracked.message_id,
                elapsed,
                exc,
            )
            return _AiClassificationOutcome(tracked.message_id, False, str(exc))

        elapsed = perf_counter() - started
        logging.info(
            "AI classified %s in %.2fs -> %s%s",
            tracked.message_id,
            elapsed,
            ",".join(tag_keys),
            " + unstarred" if classification.should_unstar() else "",
        )
        return _AiClassificationOutcome(tracked.message_id, True)

    def _classify_unclassified_active(self) -> tuple[int, tuple[SyncError, ...]]:
        eligible, errors = self._eligible_unclassified()
        self._progress(
            phase="tracking-ai",
            label="TrackingBox: AI初期分類",
            current=0,
            total=len(eligible),
            errors=len(errors),
        )
        if not eligible:
            return 0, tuple(errors)

        workers = min(self.config.ai.max_workers, len(eligible))
        logging.info(
            "AI classification starting: %d messages, %d worker(s)",
            len(eligible),
            workers,
        )
        started = perf_counter()
        classified = 0

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="wib-ai") as executor:
            futures = {executor.submit(self._classify_one, tracked): tracked for tracked in eligible}
            for current, future in enumerate(as_completed(futures), start=1):
                outcome = future.result()
                if outcome.classified:
                    classified += 1
                elif outcome.error is not None:
                    errors.append(SyncError(outcome.message_id, outcome.error))
                self._progress(
                    phase="tracking-ai",
                    label="TrackingBox: AI初期分類",
                    current=current,
                    total=len(eligible),
                    errors=len(errors),
                )

        logging.info(
            "AI classification finished: %d/%d messages in %.2fs",
            classified,
            len(eligible),
            perf_counter() - started,
        )
        return classified, tuple(errors)

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


class DeadlineService:
    def __init__(
        self,
        config: AppConfig,
        *,
        database: EmailDatabase | None = None,
    ) -> None:
        self.config = config
        self.database = database or EmailDatabase(config.database.path)

    def candidates(self, message_id: str) -> list[DeadlineCandidate]:
        self.database.initialize()
        return self.database.deadline_candidates(message_id)

    def deadlines(self, message_id: str) -> list[Deadline]:
        self.database.initialize()
        return self.database.deadlines(message_id)

    def add_candidate(
        self,
        message_id: str,
        title: str,
        *,
        due_at: str | None = None,
        source_text: str | None = None,
        created_by: DeadlineCreatedBy = DeadlineCreatedBy.USER,
        needs_review: bool = False,
    ) -> DeadlineCandidate:
        self.database.initialize()
        if self.database.email_message(message_id) is None:
            raise ValueError(f"Unknown source message: {message_id}")
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("deadline title must not be empty")
        return self.database.add_deadline_candidate(
            message_id,
            normalized_title,
            due_at=due_at,
            source_text=source_text,
            created_by=created_by,
            needs_review=needs_review,
        )

    def revise_candidate(
        self,
        candidate_id: int,
        *,
        title: str,
        due_at: str | None,
        source_text: str | None,
        needs_review: bool,
    ) -> DeadlineCandidate:
        self.database.initialize()
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("deadline title must not be empty")
        normalized_due_at = normalize_due_at(due_at) if due_at is not None else None
        return self.database.update_deadline_candidate(
            candidate_id,
            title=normalized_title,
            due_at=normalized_due_at,
            source_text=source_text,
            needs_review=needs_review,
        )

    def reject_candidate(self, candidate_id: int) -> DeadlineCandidate:
        self.database.initialize()
        return self.database.reject_deadline_candidate(candidate_id)

    def register_candidate(
        self,
        candidate_id: int,
        *,
        timezone_name: str | None = None,
        description: str | None = None,
    ) -> Deadline:
        self.database.initialize()
        candidate = self.database.deadline_candidate(candidate_id)
        if candidate is None:
            raise ValueError("deadline candidate is missing or already resolved")
        if candidate.due_at is None:
            raise ValueError("deadline candidate has no due_at")
        normalized_due_at = normalize_due_at(candidate.due_at)
        if normalized_due_at != candidate.due_at:
            self.database.update_deadline_candidate(
                candidate_id,
                title=candidate.title,
                due_at=normalized_due_at,
                source_text=candidate.source_text,
                needs_review=candidate.needs_review,
            )
        return self.database.register_deadline_candidate(
            candidate_id,
            timezone_name=timezone_name,
            description=description,
        )


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
        references: list[ImapReference] = []
        identity_errors: dict[str, str] = {}
        for email in emails:
            if email.uid is None or email.uidvalidity is None or email.mailbox is None:
                identity_errors[email.message_id] = "IMAP identity is unavailable"
                continue
            if email.mailbox != self.config.imap.mailbox:
                identity_errors[email.message_id] = (
                    f"mailbox mismatch: {email.mailbox}"
                )
                continue
            references.append(
                ImapReference(
                    email.message_id,
                    email.mailbox,
                    email.uidvalidity,
                    email.uid,
                )
            )

        snapshots: dict[str, ImapFlagsSnapshot] = {}
        errors = dict(identity_errors)
        batch_reader = getattr(self.imap_client, "inspect_flags_many", None)
        if callable(batch_reader):
            try:
                batch_snapshots, batch_errors = batch_reader(references)
                snapshots.update(batch_snapshots)
                errors.update(batch_errors)
            except (OSError, RuntimeError, ValueError) as exc:
                errors.update(
                    {reference.message_id: str(exc) for reference in references}
                )
        else:
            for reference in references:
                try:
                    snapshots[reference.message_id] = self.imap_client.inspect_flags(
                        reference.uid,
                        expected_uidvalidity=reference.uidvalidity,
                    )
                except (OSError, RuntimeError) as exc:
                    errors[reference.message_id] = str(exc)

        views: list[TrackedEmailTagView] = []
        for email in emails:
            snapshot = snapshots.get(email.message_id)
            error = errors.get(email.message_id)
            if snapshot is None:
                views.append(
                    TrackedEmailTagView(
                        email=email,
                        tags=(),
                        error=error or "IMAP flags are unavailable",
                    )
                )
                continue
            views.append(
                TrackedEmailTagView(
                    email=email,
                    tags=definitions_for_flags(snapshot.flags),
                )
            )
        return views

    def pending_emails(self) -> list[PendingEmailView]:
        self.database.initialize()
        views: list[PendingEmailView] = []
        for email in self.database.list_tracked_emails(active=True):
            if email.uid is None or email.uidvalidity is None or email.mailbox is None:
                continue
            if email.mailbox != self.config.imap.mailbox:
                continue
            try:
                snapshot = self.imap_client.inspect_flags(
                    email.uid,
                    expected_uidvalidity=email.uidvalidity,
                )
            except (OSError, RuntimeError) as exc:
                logging.warning(
                    "Pending view IMAP check failed for %s: %s",
                    email.message_id,
                    exc,
                )
                continue
            if "wib-pending" not in snapshot.flags:
                continue
            message = self.database.email_message(email.message_id)
            views.append(
                PendingEmailView(
                    email=email,
                    tags=definitions_for_flags(snapshot.flags),
                    body=message.body if message is not None else None,
                )
            )
        return views

    def resolve_pending(self, message_id: str, resolution: str) -> None:
        try:
            target_keys = _PENDING_RESOLUTIONS[resolution]
        except KeyError as exc:
            raise ValueError(f"Unknown pending resolution: {resolution!r}") from exc

        self.database.initialize()
        reference = self.database.imap_reference(message_id)
        if reference is None:
            raise RuntimeError(f"IMAP identity is unavailable for {message_id}")
        if reference.mailbox != self.config.imap.mailbox:
            raise RuntimeError(
                f"Mail is stored in {reference.mailbox!r}, not configured mailbox "
                f"{self.config.imap.mailbox!r}"
            )

        snapshot = self.imap_client.inspect_flags(
            reference.uid,
            expected_uidvalidity=reference.uidvalidity,
        )
        if "wib-pending" not in snapshot.flags:
            raise RuntimeError("Mail is no longer pending classification")

        self.imap_client.set_keywords(
            reference.uid,
            target_keys,
            enabled=True,
            expected_uidvalidity=reference.uidvalidity,
        )
        if {"wib-schedule", "wib-deadline"}.intersection(target_keys):
            relation_store = TriageRelationStore(self.config.database.path)
            relation_store.initialize()
            relation_store.ensure_workflow_focus(message_id)
        remove_keys = tuple(
            key
            for key in _NORMAL_RESOLUTION_KEYS
            if key not in target_keys and key in snapshot.flags
        )
        if remove_keys:
            self.imap_client.set_keywords(
                reference.uid,
                remove_keys,
                enabled=False,
                expected_uidvalidity=reference.uidvalidity,
            )

        if resolution == "none":
            try:
                self.imap_client.set_flagged(
                    reference.uid,
                    enabled=False,
                    expected_uidvalidity=reference.uidvalidity,
                )
            except (OSError, RuntimeError, ValueError):
                try:
                    self.imap_client.set_keywords(
                        reference.uid,
                        target_keys,
                        enabled=False,
                        expected_uidvalidity=reference.uidvalidity,
                    )
                    self.imap_client.set_keyword(
                        reference.uid,
                        "wib-pending",
                        enabled=True,
                        expected_uidvalidity=reference.uidvalidity,
                    )
                except (OSError, RuntimeError, ValueError):
                    logging.exception(
                        "Failed to roll back pending no-action resolution for %s",
                        message_id,
                    )
                raise
            self.database.update_tracking_status(
                message_id,
                TrackingStatus.INACTIVE_UNSTARRED,
            )

    def set_tag(self, message_id: str, key: str, *, enabled: bool) -> None:
        tag = require_work_tag(key)
        self.database.initialize()

        target_message_ids = [message_id]
        relation_store = TriageRelationStore(self.config.database.path)
        relation_store.initialize()
        if key == "wib-schedule-done":
            origin_message_id = relation_store.origin_for(message_id)
            if origin_message_id is not None and origin_message_id != message_id:
                target_message_ids.append(origin_message_id)

        source_reference = None
        for target_message_id in dict.fromkeys(target_message_ids):
            reference = self.database.imap_reference(target_message_id)
            if reference is None:
                raise RuntimeError(f"IMAP identity is unavailable for {target_message_id}")
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
            if target_message_id == message_id:
                source_reference = reference
                if enabled and key in {"wib-schedule", "wib-deadline"}:
                    relation_store.ensure_workflow_focus(message_id)

        if (
            key == "wib-schedule-done"
            and enabled
            and len(target_message_ids) > 1
            and source_reference is not None
        ):
            self.imap_client.set_flagged(
                source_reference.uid,
                enabled=False,
                expected_uidvalidity=source_reference.uidvalidity,
            )
