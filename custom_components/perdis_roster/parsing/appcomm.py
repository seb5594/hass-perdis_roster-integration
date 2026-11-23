"""Builds a `Snapshot` from the JSON answers of an AppComm (Perdis mobile) service.

INIT does not document this service and its field names may differ between versions, so the
parser does not expect one fixed layout. It looks for the list of days anywhere in the answer
and accepts the usual spellings of each field (`date`, `datum`, `day`, ...). Times may be given
as `HH:MM` (including `25:45` past midnight), as ISO timestamps or as minutes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from ..models import Balances, Duty, Snapshot, WeekendPointEntry, WeekendPoints
from .values import classify_duty, clock_minutes, parse_date, parse_duration, parse_number, shift_times

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("date", "day", "datum", "operatingDate", "dutyDate", "tag", "dag"),
    "code": ("code", "dutyNumber", "duty", "dienst", "dienstNr", "shift", "shortName", "kuerzel", "name"),
    "start": ("start", "begin", "beginn", "startTime", "from", "von", "dutyStart"),
    "end": ("end", "ende", "endTime", "to", "bis", "dutyEnd"),
    "start_location": ("startLocation", "beginLocation", "location", "ort", "startPlace", "meldeort"),
    "end_location": ("endLocation", "endPlace", "endort"),
    "paid": ("paidMinutes", "paidTime", "duration", "workingTime", "arbeitszeit", "dauer"),
    "break": ("breakMinutes", "breakTime", "pause"),
    "lines": ("lines", "line", "linien", "linie"),
    "remark": ("remark", "comment", "text", "description", "bemerkung", "info", "absence", "absenceType"),
    "split": ("splitShift", "split", "geteilt"),
}
OVERTIME_KEYS = ("overtimeMinutes", "overtime", "timeAccount", "zeitkonto", "balance", "saldo")
VACATION_REMAINING_KEYS = ("vacationRemaining", "remainingVacation", "resturlaub", "leaveRemaining")
VACATION_PLANNED_KEYS = ("vacationPlanned", "plannedVacation", "leavePlanned")
VACATION_ENTITLEMENT_KEYS = ("vacationEntitlement", "urlaubsanspruch", "leaveEntitlement")
POINTS_KEYS = ("points", "weekendPoints", "wePunkte", "punkte")
AVERAGE_KEYS = ("groupAverage", "average", "durchschnitt")
FREE_WEEKENDS_KEYS = ("freeWeekends", "freieWochenenden")


@dataclass(slots=True)
class AppCommAnswers:
    """The decoded JSON answers of the AppComm service; a missing answer stays empty."""

    roster: Any = None
    balances: dict[str, Any] = field(default_factory=dict)
    weekend_points: dict[str, Any] = field(default_factory=dict)


def pick(item: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    """The value of the first alias present in `item`, ignoring the case of the keys."""
    lowered = {key.lower(): value for key, value in item.items()}
    for alias in aliases:
        value = lowered.get(alias.lower())
        if value not in (None, ""):
            return value
    return None


def find_day_list(payload: Any) -> list[dict[str, Any]]:
    """The first list in the answer whose objects carry a date."""
    if isinstance(payload, list):
        if payload and all(isinstance(item, dict) for item in payload) and pick(payload[0], FIELD_ALIASES["date"]):
            return payload
        for item in payload:
            if found := find_day_list(item):
                return found
    elif isinstance(payload, dict):
        for value in payload.values():
            if found := find_day_list(value):
                return found
    return []


class AppCommParser:
    """Reads duties, accounts and weekend points from AppComm answers."""

    def __init__(self, zone: ZoneInfo) -> None:
        self._zone = zone

    def parse(self, answers: AppCommAnswers, now: datetime) -> Snapshot:
        today = now.date()
        duties = [duty for item in find_day_list(answers.roster) if (duty := self._duty(item, today))]
        return Snapshot(
            fetched_at=now,
            duties=sorted(duties, key=lambda duty: duty.day),
            balances=self._balances(answers.balances),
            weekend_points=self._weekend_points(answers.weekend_points, today),
        )

    def _duty(self, item: dict[str, Any], today: date) -> Duty | None:
        day = _date(pick(item, FIELD_ALIASES["date"]), today)
        if day is None:
            return None
        code = str(pick(item, FIELD_ALIASES["code"]) or "").strip()
        remark = pick(item, FIELD_ALIASES["remark"])
        remark = str(remark) if remark is not None else None
        duty = Duty(day=day, code=code, remark=remark)
        start, end = pick(item, FIELD_ALIASES["start"]), pick(item, FIELD_ALIASES["end"])
        if start is not None and end is not None:
            duty.start, duty.end = self._times(day, start, end)
        duty.lines = _lines(pick(item, FIELD_ALIASES["lines"]))
        duty.start_location = _text(pick(item, FIELD_ALIASES["start_location"]))
        duty.end_location = _text(pick(item, FIELD_ALIASES["end_location"])) or duty.start_location
        duty.paid_minutes = _minutes(pick(item, FIELD_ALIASES["paid"]))
        duty.break_minutes = _minutes(pick(item, FIELD_ALIASES["break"]))
        duty.split = bool(pick(item, FIELD_ALIASES["split"]))
        duty.duty_type = classify_duty(code, remark or "", duty.has_times)
        return duty

    def _times(self, day: date, start: Any, end: Any) -> tuple[datetime | None, datetime | None]:
        if isinstance(start, str) and "T" in start and isinstance(end, str) and "T" in end:
            parsed = datetime.fromisoformat(start), datetime.fromisoformat(end)
            return tuple(value if value.tzinfo else value.replace(tzinfo=self._zone) for value in parsed)
        start_minutes, end_minutes = _clock(start), _clock(end)
        if start_minutes is None or end_minutes is None:
            return None, None
        return shift_times(day, start_minutes, end_minutes, self._zone)

    @staticmethod
    def _balances(data: dict[str, Any]) -> Balances:
        return Balances(
            overtime_minutes=_minutes(pick(data, OVERTIME_KEYS)),
            vacation_remaining_days=_number(pick(data, VACATION_REMAINING_KEYS)),
            vacation_planned_days=_number(pick(data, VACATION_PLANNED_KEYS)),
            vacation_entitlement_days=_number(pick(data, VACATION_ENTITLEMENT_KEYS)),
            raw={str(key): str(value) for key, value in data.items() if not isinstance(value, (dict, list))},
        )

    @staticmethod
    def _weekend_points(data: dict[str, Any], today: date) -> WeekendPoints:
        free = _number(pick(data, FREE_WEEKENDS_KEYS))
        entries = []
        for item in find_day_list(data):
            day, points = _date(pick(item, FIELD_ALIASES["date"]), today), _number(pick(item, POINTS_KEYS))
            if day and points is not None:
                entries.append(WeekendPointEntry(day, str(pick(item, ("category", "type", "art")) or ""), points))
        return WeekendPoints(
            points=_number(pick(data, POINTS_KEYS)),
            group_average=_number(pick(data, AVERAGE_KEYS)),
            free_weekends=int(free) if free is not None else None,
            entries=entries,
        )


def _date(value: Any, today: date) -> date | None:
    if not value:
        return None
    text = str(value)
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return parse_date(text, today)


def _clock(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)  # minutes after the start of the operating day
    return clock_minutes(str(value))


def _minutes(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return parse_duration(str(value))


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return parse_number(str(value))


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def _lines(value: Any) -> tuple[str, ...]:
    """Lines may come as a list (`["705", "U79"]`) or as one text (`"705, U79"`)."""
    if not value:
        return ()
    items = value if isinstance(value, list) else str(value).replace(";", ",").split(",")
    return tuple(text for item in items if (text := str(item).strip()))
