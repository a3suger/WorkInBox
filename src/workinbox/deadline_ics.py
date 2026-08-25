from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .application import DeadlineService
from .deadline_dates import normalize_due_at
from .models import Deadline


class DeadlineIcsService:
    def __init__(self, deadline_service: DeadlineService) -> None:
        self.deadline_service = deadline_service

    def render(self, *, source_base_url: str | None = None) -> str:
        deadlines: list[Deadline] = []
        for message_id in sorted(self.deadline_service.database.message_ids()):
            deadlines.extend(self.deadline_service.deadlines(message_id))
        deadlines.sort(key=lambda item: (item.due_at, item.id))

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//WorkInBox//Deadline Calendar//JA",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:WorkInBox Deadlines",
        ]
        for deadline in deadlines:
            lines.extend(self._vtodo_lines(deadline, source_base_url=source_base_url))
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"

    def _vtodo_lines(
        self,
        deadline: Deadline,
        *,
        source_base_url: str | None,
    ) -> list[str]:
        updated = self._utc_timestamp(deadline.updated_at)
        lines = [
            "BEGIN:VTODO",
            f"UID:workinbox-deadline-{deadline.id}@workinbox.local",
            f"DTSTAMP:{updated}",
            f"LAST-MODIFIED:{updated}",
            f"SUMMARY:{_escape_text(deadline.title)}",
            self._due_line(deadline),
            "STATUS:NEEDS-ACTION",
            "CATEGORIES:WorkInBox",
            f"X-WORKINBOX-DEADLINE-ID:{deadline.id}",
            f"X-WORKINBOX-MESSAGE-ID:{_escape_text(deadline.source_message_id)}",
            f"X-WORKINBOX-CREATED-BY:{deadline.created_by.value}",
        ]
        if source_base_url:
            base_url = source_base_url.rstrip("/")
            lines.append(
                f"URL:{base_url}/deadlines/{deadline.id}/source-message"
            )
        if deadline.description:
            lines.append(f"DESCRIPTION:{_escape_text(deadline.description)}")
        lines.append("END:VTODO")
        return lines

    @staticmethod
    def _utc_timestamp(value: str) -> str:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    @staticmethod
    def _due_line(deadline: Deadline) -> str:
        value = normalize_due_at(deadline.due_at)
        if _is_date_only(value):
            parsed = date.fromisoformat(value)
            return f"DUE;VALUE=DATE:{parsed.strftime('%Y%m%d')}"

        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            if deadline.timezone:
                try:
                    zone = ZoneInfo(deadline.timezone)
                except ZoneInfoNotFoundError as exc:
                    raise ValueError(
                        f"Unknown deadline timezone: {deadline.timezone}"
                    ) from exc
                parsed = parsed.replace(tzinfo=zone)
            else:
                parsed = parsed.replace(tzinfo=timezone.utc)
        utc = parsed.astimezone(timezone.utc)
        return f"DUE:{utc.strftime('%Y%m%dT%H%M%SZ')}"


def _is_date_only(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return "T" not in value and " " not in value


def _escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\r", "\\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )
