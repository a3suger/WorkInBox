from __future__ import annotations

from dataclasses import dataclass

from .application import DeadlineService, WorkTagService
from .models import Deadline, DeadlineCandidate, DeadlineCandidateStatus


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

        return DeadlineMessageCompletion(
            message_id=message_id,
            completed=True,
            registered_count=registered_count,
            rejected_count=rejected_count,
        )
