"""Everything that can be worked out from the roster without asking the portal again.

The portal only lists duties. A driver wants to know more: when to get up, whether the rest
before the next shift is long enough, how many days are left until the next day off, when the
next free weekend comes, how many hours the week holds. `RosterInsights` answers these questions
for one point in time; the coordinator builds a new one every minute, which costs nothing but a
few comparisons.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import cached_property

try:  # StrEnum is in the standard library from Python 3.11; older cores ship a backport.
    from enum import StrEnum
except ImportError:  # pragma: no cover - only on Home Assistant cores before 2024
    from homeassistant.backports.enum import StrEnum

from .models import Duty, Snapshot


class ShiftCategory(StrEnum):
    """When a shift lies in the day; split shifts form their own category."""

    EARLY = "early"
    DAY = "day"
    LATE = "late"
    NIGHT = "night"
    SPLIT = "split"


# Start hour boundaries: a shift that starts before 04:00 or from 21:00 on is a night shift.
EARLY_FROM, DAY_FROM, LATE_FROM, NIGHT_FROM = 4, 10, 13, 21


def shift_category(duty: Duty) -> ShiftCategory | None:
    """The category of a working duty with times; None for days off and duties without times."""
    if not duty.is_working or duty.start is None:
        return None
    if duty.split:
        return ShiftCategory.SPLIT
    hour = duty.start.hour
    if hour < EARLY_FROM or hour >= NIGHT_FROM:
        return ShiftCategory.NIGHT
    if hour < DAY_FROM:
        return ShiftCategory.EARLY
    if hour < LATE_FROM:
        return ShiftCategory.DAY
    return ShiftCategory.LATE


@dataclass(frozen=True, slots=True)
class InsightSettings:
    """The personal values the derived information depends on."""

    wake_up_lead: timedelta
    commute: timedelta
    minimum_rest: timedelta


class RosterInsights:
    """Derived facts of one snapshot at one moment."""

    def __init__(self, snapshot: Snapshot | None, now: datetime, settings: InsightSettings) -> None:
        self.now = now
        self.today = now.date()
        self.settings = settings
        self.duties: list[Duty] = snapshot.duties if snapshot else []
        self._by_day = {duty.day: duty for duty in self.duties}

    def duty_on(self, day: date) -> Duty | None:
        return self._by_day.get(day)

    # --- Shifts ------------------------------------------------------------------------------

    @cached_property
    def _timed_shifts(self) -> list[Duty]:
        return sorted((duty for duty in self.duties if duty.is_working and duty.has_times),
                      key=lambda duty: duty.start)

    @cached_property
    def current_shift(self) -> Duty | None:
        """The shift that is running right now."""
        return next((duty for duty in self._timed_shifts if duty.start <= self.now < duty.end), None)

    @cached_property
    def upcoming_shift(self) -> Duty | None:
        """The next shift that has not started yet."""
        return next((duty for duty in self._timed_shifts if duty.start > self.now), None)

    @property
    def next_shift(self) -> Duty | None:
        """The running shift, otherwise the upcoming one: what a driver means by "my next shift"."""
        return self.current_shift or self.upcoming_shift

    @property
    def on_duty(self) -> bool:
        return self.current_shift is not None

    @property
    def wake_up_time(self) -> datetime | None:
        shift = self.upcoming_shift
        return shift.start - self.settings.wake_up_lead if shift else None

    @property
    def leave_home_time(self) -> datetime | None:
        shift = self.upcoming_shift
        return shift.start - self.settings.commute if shift else None

    @cached_property
    def previous_shift_end(self) -> datetime | None:
        """End of the last shift before the upcoming one."""
        shift = self.upcoming_shift
        if shift is None:
            return None
        ends = [duty.end for duty in self._timed_shifts if duty.end <= shift.start and duty is not shift]
        return max(ends, default=None)

    @property
    def rest_before_upcoming(self) -> timedelta | None:
        """The rest between the previous shift and the upcoming one."""
        if self.upcoming_shift is None or self.previous_shift_end is None:
            return None
        return self.upcoming_shift.start - self.previous_shift_end

    @property
    def short_rest(self) -> bool:
        rest = self.rest_before_upcoming
        return rest is not None and rest < self.settings.minimum_rest

    @property
    def next_shift_category(self) -> ShiftCategory | None:
        return shift_category(self.next_shift) if self.next_shift else None

    # --- Days --------------------------------------------------------------------------------

    @property
    def today_duty(self) -> Duty | None:
        return self.duty_on(self.today)

    @property
    def tomorrow_duty(self) -> Duty | None:
        return self.duty_on(self.today + timedelta(days=1))

    @cached_property
    def next_day_off(self) -> Duty | None:
        """Today when it is off, otherwise the next day off of the roster."""
        return next((duty for duty in self.duties if duty.day >= self.today and duty.is_off), None)

    @property
    def days_until_day_off(self) -> int | None:
        return (self.next_day_off.day - self.today).days if self.next_day_off else None

    @cached_property
    def working_days_in_a_row(self) -> int:
        """Working days from today on until the next day off (0 when today is off)."""
        count, day = 0, self.today
        while (duty := self.duty_on(day)) is not None and duty.is_working:
            count += 1
            day += timedelta(days=1)
        return count

    @cached_property
    def free_weekends(self) -> list[date]:
        """Saturdays from this weekend on where Saturday and Sunday are both off."""
        # On a Sunday the weekend that is still running counts too.
        start = self.today - timedelta(days=1) if self.today.weekday() == 6 else self.today
        saturdays = []
        for duty in self.duties:
            if duty.day < start or duty.day.weekday() != 5 or not duty.is_off:
                continue
            sunday = self.duty_on(duty.day + timedelta(days=1))
            if sunday is not None and sunday.is_off:
                saturdays.append(duty.day)
        return saturdays

    @property
    def next_free_weekend(self) -> date | None:
        return self.free_weekends[0] if self.free_weekends else None

    # --- Periods -----------------------------------------------------------------------------

    def planned_minutes(self, first: date, last: date) -> int:
        """Planned working minutes of the duties between two days (both included)."""
        return sum(duty.worked_minutes or 0 for duty in self.duties
                   if first <= duty.day <= last and duty.is_working)

    @property
    def week(self) -> tuple[date, date]:
        monday = self.today - timedelta(days=self.today.weekday())
        return monday, monday + timedelta(days=6)

    @property
    def month(self) -> tuple[date, date]:
        first = self.today.replace(day=1)
        following = (first + timedelta(days=32)).replace(day=1)
        return first, following - timedelta(days=1)

    def summary(self, first: date, last: date) -> dict[str, int]:
        """How many duties of each type and shift category lie between two days."""
        counts: Counter[str] = Counter()
        for duty in self.duties:
            if first <= duty.day <= last:
                counts[duty.duty_type.value] += 1
                if category := shift_category(duty):
                    counts[category.value] += 1
        return dict(counts)

    def window(self, days: int) -> list[Duty]:
        """The duties from today on for the given number of days, for the dashboard cards."""
        last = self.today + timedelta(days=days - 1)
        return [duty for duty in self.duties if self.today <= duty.day <= last]
