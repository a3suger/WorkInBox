from __future__ import annotations

from dataclasses import dataclass

from .application import DeadlineService, WorkTagService
from .models import Deadline, DeadlineCandidate, DeadlineCandidateStatus, TrackingStatus


@dataclass(frozen=True, slots=True)
class DeadlineMessageCompletion:
    message_id: str
    completed: bool
    registered_count: int
    rejected_count: int


class DeadlineWorkflowService:
    def __init__(
        self,
        deadline_service: DeadlineService,
        work_tag_service: WorkTagService,
    ) -> None:
        self.deadline_service = deadline_service
        self.work_tag_service = work_tag_service

    def register_candidate(
        self,
        candidate_id: int,
        *,
        timezone_name: str | None = None,
        description: str | None = None,
    ) -> tuple[Deadline, DeadlineMessageCompletion]:
        deadline = self.deadline_service.register_candidate(
            candidate_id,
            timezone_name=timezone_name,
            description=description,
        )
        completion = self.complete_if_ready(deadline.source_message_id)
        return deadline, completion

    def reject_candidate(
        self,
        candidate_id: int,
    ) -> tuple[DeadlineCandidate, DeadlineMessageCompletion]:
        candidate = self.deadline_service.reject_candidate(candidate_id)
        completion = self.complete_if_ready(candidate.source_message_id)
        return candidate, completion

    def dismiss_no_deadline(self, message_id: str) -> DeadlineMessageCompletion:
        """End a zero-candidate deadline workflow by explicit user judgment."""
        candidates = self.deadline_service.candidates(message_id)
        if candidates:
            raise ValueError(
                "締切候補があるため、候補ごとに登録または登録しないを選択してください"
            )

        self.work_tag_service.set_tag(
            message_id,
            "wib-deadline",
            enabled=False,
        )
        self._apply_common_end_transition(message_id)
        return DeadlineMessageCompletion(
            message_id=message_id,
            completed=True,
            registered_count=0,
            rejected_count=0,
        )

    def complete_if_ready(self, message_id: str) -> DeadlineMessageCompletion:
        candidates = self.deadline_service.candidates(message_id)
        registered_count = sum(
            candidate.status == DeadlineCandidateStatus.REGISTERED
            for candidate in candidates
        )
        rejected_count = sum(
            candidate.status == DeadlineCandidateStatus.REJECTED
            for candidate in candidates
        )

        if not candidates or any(
            candidate.status == DeadlineCandidateStatus.PENDING
            for candidate in candidates
        ):
            return DeadlineMessageCompletion(
                message_id=message_id,
                completed=False,
                registered_count=registered_count,
                rejected_count=rejected_count,
            )

        if registered_count > 0:
            self.work_tag_service.set_tag(
                message_id,
                "wib-deadline-done",
                enabled=True,
            )
        else:
            self.work_tag_service.set_tag(
                message_id,
                "wib-deadline",
                enabled=False,
            )

        self._apply_common_end_transition(message_id)
        return DeadlineMessageCompletion(
            message_id=message_id,
            completed=True,
            registered_count=registered_count,
            rejected_count=rejected_count,
        )

    def _apply_common_end_transition(self, message_id: str) -> None:
        """Apply docs/design.md dedicated-workflow common end transition."""
        database = self.work_tag_service.database
        database.initialize()
        reference = database.imap_reference(message_id)
        if reference is None:
            raise RuntimeError(f"IMAP identity is unavailable for {message_id}")
        if reference.mailbox != self.work_tag_service.config.imap.mailbox:
            raise RuntimeError(
                f"Mail is stored in {reference.mailbox!r}, not configured mailbox "
                f"{self.work_tag_service.config.imap.mailbox!r}"
            )

        snapshot = self.work_tag_service.imap_client.inspect_flags(
            reference.uid,
            expected_uidvalidity=reference.uidvalidity,
        )
        flags = set(snapshot.flags)

        deadline_unfinished = (
            "wib-deadline" in flags and "wib-deadline-done" not in flags
        )
        schedule_unfinished = (
            "wib-schedule" in flags and "wib-schedule-done" not in flags
        )
        if deadline_unfinished or schedule_unfinished:
            return

        if {"wib-answer", "wib-review", "wib-watch"}.intersection(flags):
            return

        self.work_tag_service.imap_client.set_keyword(
            reference.uid,
            "wib-bulk",
            enabled=True,
            expected_uidvalidity=reference.uidvalidity,
        )
        self.work_tag_service.imap_client.set_flagged(
            reference.uid,
            enabled=False,
            expected_uidvalidity=reference.uidvalidity,
        )
        database.update_tracking_status(
            message_id,
            TrackingStatus.INACTIVE_UNSTARRED,
        )
