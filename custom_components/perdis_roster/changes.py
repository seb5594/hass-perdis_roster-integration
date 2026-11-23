"""Detecting roster changes between two refreshes, and describing them in plain words."""

from __future__ import annotations

from datetime import date, datetime

from .models import ChangeKind, Duty, ScheduleChange, Snapshot


def detect_changes(previous: Snapshot | None, current: Snapshot, today: date) -> list[ScheduleChange]:
    """Changes of today and later days; the first refresh has nothing to compare with.

    Days the portal no longer lists because they moved out of its window are not reported as
    removed: only days inside the range both snapshots cover are compared.
    """
    if previous is None or not current.duties:
        return []
    before = {duty.day: duty for duty in previous.duties if duty.day >= today}
    after = {duty.day: duty for duty in current.duties if duty.day >= today}
    last_common_day = min(max(before, default=today), max(after, default=today))
    changes = []
    for day in sorted(set(before) | set(after)):
        if day > last_common_day:
            continue
        kind = _change_kind(before.get(day), after.get(day))
        if kind:
            changes.append(ScheduleChange(day, kind, current.fetched_at, before.get(day), after.get(day)))
    return changes


def _change_kind(old: Duty | None, new: Duty | None) -> ChangeKind | None:
    if old is None and new is not None:
        return ChangeKind.ADDED if new.is_working else None
    if new is None:
        return ChangeKind.REMOVED if old is not None and old.is_working else None
    if old.fingerprint() == new.fingerprint():
        return None
    if (old.duty_type, old.code) != (new.duty_type, new.code):
        return ChangeKind.DUTY
    if (old.start, old.end) != (new.start, new.end):
        return ChangeKind.TIMES
    return ChangeKind.LOCATION


def keep_recent(history: list[ScheduleChange], limit: int) -> list[ScheduleChange]:
    """The newest `limit` changes, newest first."""
    return sorted(history, key=lambda change: change.detected_at, reverse=True)[:limit]


def changes_since(history: list[ScheduleChange], since: datetime) -> list[ScheduleChange]:
    return [change for change in history if change.detected_at >= since]


# --- Plain words for notifications and attributes ----------------------------------------------

TEXTS = {
    "en": {
        "title": "Your roster has changed",
        ChangeKind.ADDED: "{day}: new duty {after}",
        ChangeKind.REMOVED: "{day}: duty {before} was removed",
        ChangeKind.TIMES: "{day}: duty {after} now {after_times} (was {before_times})",
        ChangeKind.DUTY: "{day}: {before} became {after}",
        ChangeKind.LOCATION: "{day}: duty {after} now starts at {after_location}",
        "date_format": "%a %d %b",
    },
    "de": {
        "title": "Dein Dienstplan hat sich geändert",
        ChangeKind.ADDED: "{day}: neuer Dienst {after}",
        ChangeKind.REMOVED: "{day}: Dienst {before} wurde gestrichen",
        ChangeKind.TIMES: "{day}: Dienst {after} jetzt {after_times} (vorher {before_times})",
        ChangeKind.DUTY: "{day}: aus {before} wurde {after}",
        ChangeKind.LOCATION: "{day}: Dienst {after} beginnt jetzt in {after_location}",
        "date_format": "%d.%m.",
    },
}
WEEKDAYS_DE = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


def texts(language: str) -> dict:
    return TEXTS.get(language.split("-", 1)[0].lower(), TEXTS["en"])


def describe(change: ScheduleChange, language: str = "en") -> str:
    """One line such as `Mo 23.11.: Dienst 4711 jetzt 05:12-13:40 (vorher 06:02-14:10)`."""
    words = texts(language)
    day = change.day.strftime(words["date_format"])
    if words is TEXTS["de"]:
        day = f"{WEEKDAYS_DE[change.day.weekday()]} {day}"
    return words[change.kind].format(
        day=day,
        before=change.before.label if change.before else "–",
        after=change.after.label if change.after else "–",
        before_times=_times(change.before),
        after_times=_times(change.after),
        after_location=(change.after.start_location if change.after else None) or "–",
    )


def _times(duty: Duty | None) -> str:
    if duty is None or not duty.has_times:
        return "–"
    return f"{duty.start:%H:%M}–{duty.end:%H:%M}"
