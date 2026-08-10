from __future__ import annotations

import re
from datetime import date, datetime


_JAPANESE_WEEKDAY_SUFFIX = re.compile(
    r"\s*(?:\([月火水木金土日](?:曜日)?\)|[月火水木金土日](?:曜日)?)\s*$"
)


def normalize_due_at(value: str) -> str:
    normalized = value.strip()
    normalized = _JAPANESE_WEEKDAY_SUFFIX.sub("", normalized).strip()
    if not normalized:
        raise ValueError("deadline due_at must not be empty")

    try:
        if "T" not in normalized and " " not in normalized:
            return date.fromisoformat(normalized).isoformat()
        return datetime.fromisoformat(normalized).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"deadline due_at must be ISO 8601 date or datetime: {value!r}"
        ) from exc
