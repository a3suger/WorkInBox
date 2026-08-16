from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkTagDefinition:
    key: str
    label: str
    color: str
    category: str


WORK_TAGS: tuple[WorkTagDefinition, ...] = (
    WorkTagDefinition("wib-watch", "注目", "#7B1FA2", "work"),
    WorkTagDefinition("wib-deadline", "締切あり", "#D32F2F", "work"),
    WorkTagDefinition("wib-schedule", "スケジュール調整", "#F57C00", "work"),
    WorkTagDefinition("wib-answer", "返信必要", "#1976D2", "work"),
    WorkTagDefinition("wib-review", "見る・検討", "#039BE5", "work"),
    WorkTagDefinition("wib-pending", "判定保留", "#757575", "classification"),
    WorkTagDefinition("wib-deadline-done", "締切登録済み", "#8E2424", "completed"),
    WorkTagDefinition("wib-schedule-done", "スケジュール対応済み", "#A65300", "completed"),
    WorkTagDefinition("wib-waiting-reply", "返信待ち", "#388E3C", "waiting"),
    WorkTagDefinition("wib-waiting-action", "対応待ち", "#7CB342", "waiting"),
    WorkTagDefinition("wib-action-ready", "対応あり", "#558B2F", "waiting"),
    WorkTagDefinition("wib-requested", "依頼済み", "#795548", "history"),
    WorkTagDefinition("wib-bulk", "一括処理", "#424242", "end"),
)

WORK_TAG_BY_KEY = {tag.key: tag for tag in WORK_TAGS}
WORK_TAG_KEYS = frozenset(WORK_TAG_BY_KEY)

# Keep reading the old bulk keyword so existing mail is not made opaque by the
# keyword rename. New writes must use the canonical key above. `wib-important`
# is intentionally not aliased to `wib-watch`: the old reference-value meaning
# and the new active follow-up meaning are different concepts.
_LEGACY_FLAG_ALIASES = {
    "wib-batch": "wib-bulk",
}


def definitions_for_flags(flags: tuple[str, ...]) -> tuple[WorkTagDefinition, ...]:
    present = set(flags)
    for legacy_key, canonical_key in _LEGACY_FLAG_ALIASES.items():
        if legacy_key in present:
            present.add(canonical_key)
    return tuple(tag for tag in WORK_TAGS if tag.key in present)


def require_work_tag(key: str) -> WorkTagDefinition:
    try:
        return WORK_TAG_BY_KEY[key]
    except KeyError as exc:
        raise ValueError(f"Unknown WorkInBox tag: {key!r}") from exc
