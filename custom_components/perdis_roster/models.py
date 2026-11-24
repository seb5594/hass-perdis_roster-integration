"""Plain data classes for everything the integration reads from a Perdis portal.

The classes are portal independent: the WebComm and the AppComm parser both produce them. A value
the portal did not report stays `None` instead of a made-up zero, so sensors show "unknown"
rather than a wrong number. Every class can be written to and read from Home Assistant's
storage with `to_dict` / `from_dict`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class DutyType(StrEnum):
    """What kind of day an entry of the roster is."""

    WORK = "work"
    RESERVE = "reserve"
    TRAINING = "training"
    FREE = "free"
    VACATION = "vacation"
    COMPENSATION = "compensation"
    SICK = "sick"
    UNKNOWN = "unknown"


WORKING_TYPES = frozenset({DutyType.WORK, DutyType.RESERVE, DutyType.TRAINING})
OFF_TYPES = frozenset({DutyType.FREE, DutyType.VACATION, DutyType.COMPENSATION})


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value else None


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass(slots=True)
class DutySegment:
    """One leg of a shift: a drive, a break, a preparation or a transition between two parts.

    These come from the detail page of a shift and let the calendar and the cards show what a
    shift is made of (times, reporting points, lines), not just its start and end.
    """

    start: datetime
    end: datetime
    start_location: str | None = None
    end_location: str | None = None
    line: str | None = None
    kind: str = ""  # the portal's own short code, e.g. a drive, a break or a preparation
    is_break: bool = False
    # The relief marker the detail page prints for the leg, e.g. "+/-" or "-/-": whether the driver
    # takes a vehicle over at the start and hands it over at the end, so they know which way to relieve.
    relief: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "start_location": self.start_location,
            "end_location": self.end_location,
            "line": self.line,
            "kind": self.kind,
            "is_break": self.is_break,
            "relief": self.relief,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DutySegment:
        return cls(
            start=datetime.fromisoformat(data["start"]),
            end=datetime.fromisoformat(data["end"]),
            start_location=data.get("start_location"),
            end_location=data.get("end_location"),
            line=data.get("line"),
            kind=data.get("kind", ""),
            is_break=data.get("is_break", False),
            relief=data.get("relief", ""),
        )


@dataclass(slots=True)
class Duty:
    """One operating day of the roster: a shift, a reserve, a day off or an absence.

    Transit operating days run past midnight; `start` and `end` are real points in time, so a
    shift from 22:30 to 25:45 ends at 01:45 on the next calendar day.
    """

    day: date
    duty_type: DutyType = DutyType.UNKNOWN
    code: str = ""
    start: datetime | None = None
    end: datetime | None = None
    start_location: str | None = None
    end_location: str | None = None
    lines: tuple[str, ...] = ()
    paid_minutes: int | None = None
    break_minutes: int | None = None
    split: bool = False
    remark: str | None = None
    segments: list[DutySegment] = field(default_factory=list)

    @property
    def is_working(self) -> bool:
        return self.duty_type in WORKING_TYPES

    @property
    def is_off(self) -> bool:
        return self.duty_type in OFF_TYPES

    @property
    def has_times(self) -> bool:
        return self.start is not None and self.end is not None

    @property
    def label(self) -> str:
        """Short text for a duty: its number, or the absence code the portal shows."""
        return self.code or self.duty_type.value

    @property
    def worked_minutes(self) -> int | None:
        """Paid time when the portal reports it, otherwise the span minus the breaks."""
        if self.paid_minutes is not None:
            return self.paid_minutes
        if not self.has_times:
            return None
        span = int((self.end - self.start).total_seconds() // 60)
        return max(span - (self.break_minutes or 0), 0)

    def fingerprint(self) -> tuple[Any, ...]:
        """The parts of a duty a driver cares about; a difference counts as a roster change."""
        return (self.duty_type, self.code, self.start, self.end, self.start_location)

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day.isoformat(),
            "duty_type": self.duty_type.value,
            "code": self.code,
            "start": _iso(self.start),
            "end": _iso(self.end),
            "start_location": self.start_location,
            "end_location": self.end_location,
            "lines": list(self.lines),
            "paid_minutes": self.paid_minutes,
            "break_minutes": self.break_minutes,
            "split": self.split,
            "remark": self.remark,
            "segments": [segment.to_dict() for segment in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Duty:
        return cls(
            day=date.fromisoformat(data["day"]),
            duty_type=DutyType(data.get("duty_type", DutyType.UNKNOWN)),
            code=data.get("code", ""),
            start=_datetime(data.get("start")),
            end=_datetime(data.get("end")),
            start_location=data.get("start_location"),
            end_location=data.get("end_location"),
            lines=tuple(data.get("lines", ())),
            paid_minutes=data.get("paid_minutes"),
            break_minutes=data.get("break_minutes"),
            split=data.get("split", False),
            remark=data.get("remark"),
            segments=[DutySegment.from_dict(item) for item in data.get("segments", [])],
        )


@dataclass(slots=True)
class Balances:
    """Time and leave accounts. `raw` keeps every label/value pair the portal showed."""

    overtime_minutes: int | None = None
    target_minutes: int | None = None
    actual_minutes: int | None = None
    vacation_remaining_days: float | None = None
    vacation_planned_days: float | None = None
    vacation_entitlement_days: float | None = None
    raw: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overtime_minutes": self.overtime_minutes,
            "target_minutes": self.target_minutes,
            "actual_minutes": self.actual_minutes,
            "vacation_remaining_days": self.vacation_remaining_days,
            "vacation_planned_days": self.vacation_planned_days,
            "vacation_entitlement_days": self.vacation_entitlement_days,
            "raw": dict(self.raw),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Balances:
        return cls(**{key: data.get(key) for key in (
            "overtime_minutes", "target_minutes", "actual_minutes", "vacation_remaining_days",
            "vacation_planned_days", "vacation_entitlement_days",
        )}, raw=dict(data.get("raw") or {}))


@dataclass(slots=True)
class WeekendPointEntry:
    """One line of the weekend points ledger (a worked Saturday, Sunday or holiday)."""

    day: date
    category: str
    points: float

    def to_dict(self) -> dict[str, Any]:
        return {"day": self.day.isoformat(), "category": self.category, "points": self.points}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeekendPointEntry:
        return cls(date.fromisoformat(data["day"]), data.get("category", ""), data.get("points", 0.0))


@dataclass(slots=True)
class WeekendPoints:
    """Weekend points ("WE-Punkte"): the fairness account for weekend duties."""

    points: float | None = None
    group_average: float | None = None
    free_weekends: int | None = None
    free_weekends_target: int | None = None
    entries: list[WeekendPointEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": self.points,
            "group_average": self.group_average,
            "free_weekends": self.free_weekends,
            "free_weekends_target": self.free_weekends_target,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeekendPoints:
        return cls(
            points=data.get("points"),
            group_average=data.get("group_average"),
            free_weekends=data.get("free_weekends"),
            free_weekends_target=data.get("free_weekends_target"),
            entries=[WeekendPointEntry.from_dict(item) for item in data.get("entries", [])],
        )


@dataclass(slots=True)
class DutySwap:
    """One shift-swap offer or request listed on the portal's duty-swap page."""

    swap_id: str  # the id the portal uses to accept, reject or withdraw this entry
    day: date | None = None  # the shift's date (the "from" column), when it reads as a date
    end_day: date | None = None
    duty: str = ""
    time: str = ""  # the shift's clock time as the portal prints it, e.g. "10:22 - 18:03"
    partner: str = ""
    status: str = ""  # e.g. "offen", "angeboten", "angenommen"
    kind: str = ""  # the "Typ" column: whether it is offered to or by the driver
    fields: dict[str, str] = field(default_factory=dict)  # every column, for a detailed view

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.swap_id,
            "day": self.day.isoformat() if self.day else None,
            "end_day": self.end_day.isoformat() if self.end_day else None,
            "duty": self.duty,
            "time": self.time,
            "partner": self.partner,
            "status": self.status,
            "type": self.kind,
            "details": self.fields,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DutySwap:
        return cls(
            swap_id=data["id"],
            day=date.fromisoformat(data["day"]) if data.get("day") else None,
            end_day=date.fromisoformat(data["end_day"]) if data.get("end_day") else None,
            duty=data.get("duty", ""),
            time=data.get("time", ""),
            partner=data.get("partner", ""),
            status=data.get("status", ""),
            kind=data.get("type", ""),
            fields=data.get("details") or {},
        )


@dataclass(slots=True)
class Snapshot:
    """Everything one refresh read from the portal."""

    fetched_at: datetime
    duties: list[Duty] = field(default_factory=list)
    balances: Balances = field(default_factory=Balances)
    weekend_points: WeekendPoints = field(default_factory=WeekendPoints)
    employee_name: str | None = None
    swaps: list[DutySwap] = field(default_factory=list)
    swap_window: tuple[date, date] | None = None  # the period the portal accepts swap requests for

    def duty_on(self, day: date) -> Duty | None:
        return next((duty for duty in self.duties if duty.day == day), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fetched_at": self.fetched_at.isoformat(),
            "duties": [duty.to_dict() for duty in self.duties],
            "balances": self.balances.to_dict(),
            "weekend_points": self.weekend_points.to_dict(),
            "employee_name": self.employee_name,
            "swaps": [swap.to_dict() for swap in self.swaps],
            "swap_window": [day.isoformat() for day in self.swap_window] if self.swap_window else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        window = data.get("swap_window")
        return cls(
            fetched_at=datetime.fromisoformat(data["fetched_at"]),
            duties=[Duty.from_dict(item) for item in data.get("duties", [])],
            balances=Balances.from_dict(data.get("balances") or {}),
            weekend_points=WeekendPoints.from_dict(data.get("weekend_points") or {}),
            employee_name=data.get("employee_name"),
            swaps=[DutySwap.from_dict(item) for item in data.get("swaps", [])],
            swap_window=(date.fromisoformat(window[0]), date.fromisoformat(window[1])) if window else None,
        )


class ChangeKind(StrEnum):
    """How a day of the roster changed between two refreshes."""

    ADDED = "added"
    REMOVED = "removed"
    TIMES = "times"
    DUTY = "duty"
    LOCATION = "location"


@dataclass(slots=True)
class ScheduleChange:
    """A difference between two refreshes for one day, kept for the change history."""

    day: date
    kind: ChangeKind
    detected_at: datetime
    before: Duty | None = None
    after: Duty | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day.isoformat(),
            "kind": self.kind.value,
            "detected_at": self.detected_at.isoformat(),
            "before": self.before.to_dict() if self.before else None,
            "after": self.after.to_dict() if self.after else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduleChange:
        return cls(
            day=date.fromisoformat(data["day"]),
            kind=ChangeKind(data["kind"]),
            detected_at=datetime.fromisoformat(data["detected_at"]),
            before=Duty.from_dict(data["before"]) if data.get("before") else None,
            after=Duty.from_dict(data["after"]) if data.get("after") else None,
        )
