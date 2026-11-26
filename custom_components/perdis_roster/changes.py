"""Detecting roster changes between two refreshes, and describing them in plain words."""

from __future__ import annotations

from datetime import date, datetime

from .labels import type_label
from .models import ChangeKind, Duty, DutyType, ScheduleChange, Snapshot


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
        "change_title": "Roster change",
        "weekdays": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
        "date_format": "%d %b",
    },
    "de": {
        "change_title": "Dienstplanänderung",
        "weekdays": ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"),
        "date_format": "%d.%m.",
    },
}


def texts(language: str) -> dict:
    return TEXTS.get(language.split("-", 1)[0].lower(), TEXTS["en"])


def describe(change: ScheduleChange, language: str = "en") -> str:
    """A short, two-line summary of one change, e.g. `Freitag, 27.11. SF Neu` + `06:00 - 17:30`.

    The first line is the weekday, the date and what the day now is (its duty number, or the name of
    the absence); the second line holds the times, dropped when the day has none.
    """
    words = texts(language)
    duty = change.after or change.before
    headline = f"{words['weekdays'][change.day.weekday()]}, {change.day.strftime(words['date_format'])}"
    headline = f"{headline} {_what(duty, language)}".strip()
    # Prefer the new times; for a day that lost its times (e.g. it became an absence) show the old
    # ones so the change still carries the shift it replaced.
    times = _time_range(change.after) or _time_range(change.before)
    return f"{headline}\n{times}" if times else headline


def _what(duty: Duty | None, language: str) -> str:
    """What a day is: an unknown entry's own code, a working shift's "Dienst <number>", or a name."""
    if duty is None:
        return "–"
    if duty.duty_type is DutyType.UNKNOWN and duty.code:
        return duty.code
    if duty.is_working:
        return f"{type_label(DutyType.WORK, language)} {duty.code}".strip()
    return type_label(duty.duty_type, language)


def _time_range(duty: Duty | None) -> str:
    if duty is None or not duty.has_times:
        return ""
    return f"{duty.start:%H:%M} - {duty.end:%H:%M}"
