from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from re import fullmatch

from .application import DeadlineService
from .deadline_dates import normalize_due_at
from .models import Deadline


@dataclass(frozen=True, slots=True)
class CalDavUpdate:
    title: str
    start_at: str | None
    due_at: str
    timezone: str | None
    description: str | None
    status: str
    completed_at: str | None
    percent_complete: int
    priority: int


class DeadlineCalDavService:
    def __init__(self, deadline_service: DeadlineService) -> None:
        self.deadline_service = deadline_service

    def all(self) -> list[Deadline]:
        self.deadline_service.database.initialize()
        return self.deadline_service.database.all_deadlines()

    def get(self, deadline_id: int) -> Deadline | None:
        return self.deadline_service.deadline(deadline_id)

    @staticmethod
    def etag(deadline: Deadline) -> str:
        return f'"workinbox-deadline-{deadline.id}-v{deadline.version}"'

    def render(self, deadline: Deadline) -> str:
        updated = _utc_timestamp(deadline.updated_at)
        lines = [
            "BEGIN:VCALENDAR", "VERSION:2.0",
            "PRODID:-//WorkInBox//CalDAV Deadlines//JA", "CALSCALE:GREGORIAN",
            "BEGIN:VTODO", f"UID:{_uid(deadline.id)}", f"DTSTAMP:{updated}",
            f"CREATED:{_utc_timestamp(deadline.created_at)}",
            f"LAST-MODIFIED:{updated}", f"SUMMARY:{_escape(deadline.title)}",
        ]
        if deadline.start_at:
            lines.append(_date_line("DTSTART", deadline.start_at, deadline.timezone))
        lines.extend([
            _date_line("DUE", deadline.due_at, deadline.timezone),
            f"STATUS:{deadline.status}",
            f"PERCENT-COMPLETE:{deadline.percent_complete}",
            f"PRIORITY:{deadline.priority}",
        ])
        if deadline.completed_at:
            lines.append(f"COMPLETED:{_utc_timestamp(deadline.completed_at)}")
        if deadline.description:
            lines.append(f"DESCRIPTION:{_escape(deadline.description)}")
        message_id = deadline.source_message_id.strip("<>")
        lines.extend([
            "CATEGORIES:WorkInBox",
            f"X-WORKINBOX-DEADLINE-ID:{deadline.id}",
            f"X-WORKINBOX-MESSAGE-ID:{_escape(deadline.source_message_id)}",
            f"X-WORKINBOX-CREATED-BY:{deadline.created_by.value}",
            f"URL:mid:{message_id}", "END:VTODO", "END:VCALENDAR",
        ])
        return "\r\n".join(lines) + "\r\n"

    def update(self, deadline: Deadline, content: str) -> Deadline | None:
        values = _parse(content)
        if values.get("UID", (None, ""))[1] != _uid(deadline.id):
            raise ValueError("UID cannot be changed")
        if values.get("X-WORKINBOX-DEADLINE-ID", (None, ""))[1] != str(deadline.id):
            raise ValueError("deadline ID cannot be changed")
        if _unescape(values.get("X-WORKINBOX-MESSAGE-ID", (None, ""))[1]) != deadline.source_message_id:
            raise ValueError("source Message-ID cannot be changed")
        title = _unescape(_required(values, "SUMMARY")).strip()
        if not title:
            raise ValueError("SUMMARY must not be empty")
        due_at, timezone_name = _parse_date(values, "DUE")
        start_at = _parse_date(values, "DTSTART")[0] if "DTSTART" in values else None
        if start_at:
            start_kind, start_value = _comparable(start_at)
            due_kind, due_value = _comparable(due_at)
            if start_kind != due_kind:
                raise ValueError("DTSTART and DUE must use the same value type")
            if start_value > due_value:
                raise ValueError("DTSTART must not be later than DUE")
        status = values.get("STATUS", (None, "NEEDS-ACTION"))[1].upper()
        percent = int(values.get("PERCENT-COMPLETE", (None, "0"))[1])
        completed = _parse_timestamp(values["COMPLETED"][1]) if "COMPLETED" in values else None
        if status == "COMPLETED":
            if percent != 100 or completed is None:
                raise ValueError("completed ToDo requires 100 percent and COMPLETED")
        elif status == "NEEDS-ACTION":
            if percent != 0 or completed is not None:
                raise ValueError("open ToDo requires 0 percent and no COMPLETED")
        else:
            raise ValueError("only NEEDS-ACTION and COMPLETED are supported")
        priority = int(values.get("PRIORITY", (None, "0"))[1])
        if not 0 <= priority <= 9:
            raise ValueError("PRIORITY must be between 0 and 9")
        description = _unescape(values["DESCRIPTION"][1]).strip() if "DESCRIPTION" in values else None
        return self.deadline_service.database.update_deadline_from_caldav(
            deadline.id, expected_version=deadline.version, title=title,
            start_at=start_at, due_at=due_at, timezone_name=timezone_name,
            description=description or None, status=status, completed_at=completed,
            percent_complete=percent, priority=priority,
        )


def _uid(deadline_id: int) -> str:
    return f"workinbox-deadline-{deadline_id}@workinbox.local"


def _parse(content: str) -> dict[str, tuple[dict[str, str], str]]:
    unfolded = content.replace("\r\n ", "").replace("\n ", "")
    if unfolded.upper().count("BEGIN:VTODO") != 1:
        raise ValueError("exactly one VTODO is required")
    result: dict[str, tuple[dict[str, str], str]] = {}
    for raw in unfolded.replace("\r\n", "\n").split("\n"):
        if ":" not in raw:
            continue
        head, value = raw.split(":", 1)
        parts = head.split(";")
        name = parts[0].upper()
        params = {k.upper(): v for part in parts[1:] if "=" in part for k, v in [part.split("=", 1)]}
        result[name] = (params, value)
    return result


def _required(values: dict[str, tuple[dict[str, str], str]], name: str) -> str:
    if name not in values:
        raise ValueError(f"{name} is required")
    return values[name][1]


def _parse_date(values: dict[str, tuple[dict[str, str], str]], name: str) -> tuple[str, str | None]:
    params, raw = values[name]
    if params.get("VALUE", "").upper() == "DATE" or fullmatch(r"\d{8}", raw):
        return datetime.strptime(raw, "%Y%m%d").date().isoformat(), None
    parsed = datetime.strptime(raw, "%Y%m%dT%H%M%SZ") if raw.endswith("Z") else datetime.strptime(raw, "%Y%m%dT%H%M%S")
    if raw.endswith("Z"):
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat(), params.get("TZID")


def _parse_timestamp(raw: str) -> str:
    parsed = datetime.strptime(raw, "%Y%m%dT%H%M%SZ")
    return parsed.replace(tzinfo=timezone.utc).isoformat()


def _comparable(value: str) -> tuple[int, str]:
    normalized = normalize_due_at(value)
    return (0 if "T" not in normalized else 1, normalized)


def _date_line(name: str, value: str, timezone_name: str | None) -> str:
    value = normalize_due_at(value)
    if "T" not in value and " " not in value:
        return f"{name};VALUE=DATE:{date.fromisoformat(value).strftime('%Y%m%d')}"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        return f"{name}:{parsed.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    suffix = f";TZID={timezone_name}" if timezone_name else ""
    return f"{name}{suffix}:{parsed.strftime('%Y%m%dT%H%M%S')}"


def _utc_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\r\n", "\\n").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def _unescape(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
