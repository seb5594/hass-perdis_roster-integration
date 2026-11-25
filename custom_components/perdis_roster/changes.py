"""Detecting roster changes between two refreshes, and describing them in plain words."""

from __future__ import annotations

from datetime import date, datetime

from .labels import type_label
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
        # A day that turns into an absence (a day off, vacation, sick day) reads as "entered";
        # a new or changed shift keeps its number.
        "entered": "{type} entered for {day}",
        "added_work": "New duty {after} on {day}",
        "changed_work": "Duty {after} instead of {before} on {day}",
        ChangeKind.REMOVED: "Duty {before} dropped on {day}",
        ChangeKind.TIMES: "Duty {after} now {after_times} (was {before_times}) on {day}",
        ChangeKind.LOCATION: "Duty {after} now starts at {after_location} on {day}",
        "weekdays": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
        "date_format": "%d %b",
    },
    "de": {
        "title": "Dein Dienstplan hat sich geändert",
        "entered": "{type} eingetragen für {day}",
        "added_work": "Neuer Dienst {after} am {day}",
        "changed_work": "Dienst {after} statt {before} am {day}",
        ChangeKind.REMOVED: "Dienst {before} entfällt am {day}",
        ChangeKind.TIMES: "Dienst {after} jetzt {after_times} (vorher {before_times}) am {day}",
        ChangeKind.LOCATION: "Dienst {after} beginnt jetzt in {after_location} am {day}",
        "weekdays": ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"),
        "date_format": "%d.%m.",
    },
}


def texts(language: str) -> dict:
    return TEXTS.get(language.split("-", 1)[0].lower(), TEXTS["en"])


def describe(change: ScheduleChange, language: str = "en") -> str:
    """One readable line, e.g. `Frei eingetragen für Montag, 30.11.` or
    `Dienst 4711 jetzt 05:12–13:40 (vorher 06:02–14:10) am Montag, 23.11.`."""
    words = texts(language)
    day = f"{words['weekdays'][change.day.weekday()]}, {change.day.strftime(words['date_format'])}"
    after, before = change.after, change.before
    fields = {
        "day": day,
        "before": before.label if before else "–",
        "after": after.label if after else "–",
        "before_times": _times(before),
        "after_times": _times(after),
        "after_location": (after.start_location if after else None) or "–",
    }
    if change.kind is ChangeKind.ADDED:
        template = "added_work" if after and after.is_working else "entered"
    elif change.kind is ChangeKind.DUTY:
        # Turning into an absence reads as "entered"; a swap between real shifts keeps both numbers.
        template = "changed_work" if after and after.is_working else "entered"
    else:
        template = change.kind
    if template == "entered":
        fields["type"] = type_label(after.duty_type, language) if after else fields["after"]
    return words[template].format(**fields)


def _times(duty: Duty | None) -> str:
    if duty is None or not duty.has_times:
        return "–"
    return f"{duty.start:%H:%M}–{duty.end:%H:%M}"
