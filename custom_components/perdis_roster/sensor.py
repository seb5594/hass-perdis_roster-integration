"""Sensors: the next shift, the days ahead, the accounts and the roster for the dashboard cards.

Each sensor is one `PerdisSensorDescription` with a function for its value and, where useful, one
for its attributes. Values that are worked out from the roster (rest time, days until the next
day off, planned hours, ...) come from `RosterInsights`, so all sensors agree with each other.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capabilities import (
    CAP_DAILY_VALUES,
    CAP_OVERTIME,
    CAP_ROSTER,
    CAP_SWAP,
    CAP_VACATION,
    CAP_WEEKEND_AVERAGE,
    CAP_WEEKEND_FREE,
    CAP_WEEKEND_POINTS,
)
from .changes import describe
from .coordinator import PerdisConfigEntry, PerdisCoordinator, coordinator_of
from .entity import ATTR_ROLE, PerdisEntity, description_frozen
from .insights import ShiftCategory, shift_category
from .models import Duty, DutyType

ROSTER_CARD_DAYS = 42  # how far the roster sensor looks ahead for the dashboard card
LEDGER_ENTRIES = 10
POINTS = "pts"

Value = str | int | float | date | datetime | None


@dataclass(frozen=description_frozen(SensorEntityDescription), kw_only=True)
class PerdisSensorDescription(SensorEntityDescription):
    value_fn: Callable[[PerdisCoordinator], Value]
    attributes_fn: Callable[[PerdisCoordinator], dict[str, Any]] | None = None
    role: str | None = None


def duty_attributes(duty: Duty | None) -> dict[str, Any]:
    """The details of a duty, the same for every sensor that shows one."""
    if duty is None:
        return {}
    category = shift_category(duty)
    return {
        "date": duty.day.isoformat(),
        "duty_type": duty.duty_type.value,
        "duty": duty.code or None,
        "start": duty.start.isoformat() if duty.start else None,
        "end": duty.end.isoformat() if duty.end else None,
        "start_location": duty.start_location,
        "end_location": duty.end_location,
        "lines": list(duty.lines),
        "hours": _hours(duty.worked_minutes),
        "split_shift": duty.split,
        "category": category.value if category else None,
        "remark": duty.remark,
    }


def _hours(minutes: int | None) -> float | None:
    return round(minutes / 60, 2) if minutes is not None else None


def _minutes_until(moment: datetime | None, now: datetime) -> int | None:
    return max(int((moment - now).total_seconds() // 60), 0) if moment else None


def _days_until(day: date | None, today: date) -> int | None:
    return (day - today).days if day else None


# --- Values and attributes -----------------------------------------------------------------------

def _next_shift_attributes(coordinator: PerdisCoordinator) -> dict[str, Any]:
    insights = coordinator.insights
    shift = insights.next_shift
    if shift is None:
        return {}
    rest = insights.rest_before_upcoming
    return {
        **duty_attributes(shift),
        "running": insights.on_duty,
        "minutes_until_start": _minutes_until(shift.start, insights.now),
        "minutes_until_end": _minutes_until(shift.end, insights.now),
        "wake_up": insights.wake_up_time.isoformat() if insights.wake_up_time else None,
        "leave_home": insights.leave_home_time.isoformat() if insights.leave_home_time else None,
        "rest_before_hours": round(rest.total_seconds() / 3600, 1) if rest else None,
        "short_rest": insights.short_rest,
    }


def _day_value(duty: Duty | None) -> str | None:
    return duty.duty_type.value if duty else None


def _period_attributes(coordinator: PerdisCoordinator, period: tuple[date, date]) -> dict[str, Any]:
    first, last = period
    return {"from": first.isoformat(), "to": last.isoformat(), **coordinator.insights.summary(first, last)}


def _overtime_attributes(coordinator: PerdisCoordinator) -> dict[str, Any]:
    balances = coordinator.data.snapshot.balances
    return {
        "target_hours": _hours(balances.target_minutes),
        "actual_hours": _hours(balances.actual_minutes),
        "all_balances": balances.raw,
    }


def _daily_entry_hours(entry) -> dict[str, Any]:
    """One day of the Tageswerte page as hours, plus every raw column the portal showed."""
    return {
        "date": entry.day.isoformat(),
        "target_hours": _hours(entry.target_minutes),
        "actual_hours": _hours(entry.actual_minutes),
        "balance_hours": _hours(entry.balance_minutes),
        "account_hours": _hours(entry.cumulative_minutes),
        "cells": entry.cells,
    }


def _daily_balance_value(coordinator: PerdisCoordinator) -> float | None:
    current = _snapshot(coordinator).daily_values.current(coordinator.insights.today)
    return _hours(current.balance_minutes) if current else None


def _daily_values_attributes(coordinator: PerdisCoordinator) -> dict[str, Any]:
    daily = _snapshot(coordinator).daily_values
    current = daily.current(coordinator.insights.today)
    attributes = _daily_entry_hours(current) if current else {}
    return {
        **attributes,
        "columns": list(daily.columns),
        "recent": [_daily_entry_hours(entry) for entry in daily.entries[-LEDGER_ENTRIES:]],
    }


def _vacation_attributes(coordinator: PerdisCoordinator) -> dict[str, Any]:
    balances = coordinator.data.snapshot.balances
    remaining, planned = balances.vacation_remaining_days, balances.vacation_planned_days
    return {
        "planned_days": planned,
        "entitlement_days": balances.vacation_entitlement_days,
        "left_after_planned_days": remaining - planned if remaining is not None and planned is not None else None,
    }


def _points_difference(coordinator: PerdisCoordinator) -> float | None:
    points = coordinator.data.snapshot.weekend_points
    if points.points is None or points.group_average is None:
        return None
    return round(points.points - points.group_average, 2)


def _weekend_points_attributes(coordinator: PerdisCoordinator) -> dict[str, Any]:
    points = coordinator.data.snapshot.weekend_points
    return {
        "group_average": points.group_average,
        "difference_to_average": _points_difference(coordinator),
        "free_weekends": points.free_weekends,
        "recent_entries": [entry.to_dict() for entry in points.entries[-LEDGER_ENTRIES:]],
    }


def _roster_attributes(coordinator: PerdisCoordinator) -> dict[str, Any]:
    changed_days = {change.day.isoformat() for change in coordinator.data.recent_changes}
    days = []
    for duty in coordinator.insights.window(ROSTER_CARD_DAYS):
        attributes = duty_attributes(duty)
        days.append({**attributes, "changed": attributes["date"] in changed_days})
    return {
        "days": days,
        "free_weekends": [saturday.isoformat() for saturday in coordinator.insights.free_weekends],
        "employee": coordinator.data.snapshot.employee_name,
        "online": coordinator.data.online,
    }


def _changes_attributes(coordinator: PerdisCoordinator) -> dict[str, Any]:
    language = coordinator.hass.config.language or "en"
    return {"changes": [
        {**change.to_dict(), "summary": describe(change, language)} for change in coordinator.data.recent_changes
    ]}


def _swap_attributes(coordinator: PerdisCoordinator) -> dict[str, Any]:
    window = coordinator.swap_window
    return {
        "swaps": [swap.to_dict() for swap in coordinator.swaps],
        "request_from": window[0].isoformat() if window else None,
        "request_to": window[1].isoformat() if window else None,
    }


def _snapshot(coordinator: PerdisCoordinator):
    return coordinator.data.snapshot


SENSORS: tuple[PerdisSensorDescription, ...] = (
    # Next shift
    PerdisSensorDescription(
        key="next_shift", role="next_shift",
        value_fn=lambda c: c.insights.next_shift.label if c.insights.next_shift else None,
        attributes_fn=_next_shift_attributes,
    ),
    PerdisSensorDescription(
        key="next_shift_start", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.insights.next_shift.start if c.insights.next_shift else None,
    ),
    PerdisSensorDescription(
        key="next_shift_end", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.insights.next_shift.end if c.insights.next_shift else None,
    ),
    PerdisSensorDescription(
        key="next_shift_location",
        value_fn=lambda c: c.insights.next_shift.start_location if c.insights.next_shift else None,
    ),
    PerdisSensorDescription(
        key="next_shift_category", device_class=SensorDeviceClass.ENUM, options=[c.value for c in ShiftCategory],
        value_fn=lambda c: c.insights.next_shift_category.value if c.insights.next_shift_category else None,
    ),
    PerdisSensorDescription(
        key="wake_up", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.insights.wake_up_time,
        attributes_fn=lambda c: {"lead_minutes": int(c.settings.wake_up_lead.total_seconds() // 60)},
    ),
    PerdisSensorDescription(
        key="leave_home", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.insights.leave_home_time,
        attributes_fn=lambda c: {"commute_minutes": int(c.settings.commute.total_seconds() // 60)},
    ),
    PerdisSensorDescription(
        key="rest_before_next_shift", device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS, suggested_display_precision=1,
        value_fn=lambda c: round(r.total_seconds() / 3600, 2) if (r := c.insights.rest_before_upcoming) else None,
        attributes_fn=lambda c: {"minimum_hours": c.settings.minimum_rest.total_seconds() / 3600,
                                 "short_rest": c.insights.short_rest},
    ),
    # Days
    PerdisSensorDescription(
        key="today", device_class=SensorDeviceClass.ENUM, options=[t.value for t in DutyType],
        value_fn=lambda c: _day_value(c.insights.today_duty),
        attributes_fn=lambda c: duty_attributes(c.insights.today_duty),
    ),
    PerdisSensorDescription(
        key="tomorrow", device_class=SensorDeviceClass.ENUM, options=[t.value for t in DutyType],
        value_fn=lambda c: _day_value(c.insights.tomorrow_duty),
        attributes_fn=lambda c: duty_attributes(c.insights.tomorrow_duty),
    ),
    PerdisSensorDescription(
        key="next_day_off", device_class=SensorDeviceClass.DATE,
        value_fn=lambda c: c.insights.next_day_off.day if c.insights.next_day_off else None,
        attributes_fn=lambda c: {"days_until": c.insights.days_until_day_off,
                                 **duty_attributes(c.insights.next_day_off)},
    ),
    PerdisSensorDescription(
        key="days_until_day_off", native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda c: c.insights.days_until_day_off,
    ),
    PerdisSensorDescription(
        key="working_days_in_a_row", native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda c: c.insights.working_days_in_a_row,
    ),
    PerdisSensorDescription(
        key="next_free_weekend", role="next_free_weekend", device_class=SensorDeviceClass.DATE,
        value_fn=lambda c: c.insights.next_free_weekend,
        attributes_fn=lambda c: {"days_until": _days_until(c.insights.next_free_weekend, c.insights.today),
                                 "all": [day.isoformat() for day in c.insights.free_weekends]},
    ),
    PerdisSensorDescription(
        key="free_weekends_ahead", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: len(c.insights.free_weekends),
    ),
    PerdisSensorDescription(
        key="planned_hours_week", role="planned_week", device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS, suggested_display_precision=1,
        value_fn=lambda c: _hours(c.insights.planned_minutes(*c.insights.week)),
        attributes_fn=lambda c: _period_attributes(c, c.insights.week),
    ),
    PerdisSensorDescription(
        key="planned_hours_month", device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS, suggested_display_precision=1,
        value_fn=lambda c: _hours(c.insights.planned_minutes(*c.insights.month)),
        attributes_fn=lambda c: _period_attributes(c, c.insights.month),
    ),
    # Accounts
    PerdisSensorDescription(
        key="overtime", role="overtime", device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        value_fn=lambda c: _hours(_snapshot(c).balances.overtime_minutes),
        attributes_fn=_overtime_attributes,
    ),
    PerdisSensorDescription(
        key="daily_balance", role="daily_values", device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        value_fn=_daily_balance_value,
        attributes_fn=_daily_values_attributes,
    ),
    PerdisSensorDescription(
        key="vacation_remaining", role="vacation", state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda c: _snapshot(c).balances.vacation_remaining_days,
        attributes_fn=_vacation_attributes,
    ),
    PerdisSensorDescription(
        key="weekend_points", role="weekend_points", state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POINTS,
        value_fn=lambda c: _snapshot(c).weekend_points.points,
        attributes_fn=_weekend_points_attributes,
    ),
    PerdisSensorDescription(
        key="weekend_points_difference", role="weekend_points_difference", state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POINTS, value_fn=_points_difference,
    ),
    PerdisSensorDescription(
        key="free_weekends_year", role="free_weekends", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _snapshot(c).weekend_points.free_weekends,
        attributes_fn=lambda c: {"target": _snapshot(c).weekend_points.free_weekends_target},
    ),
    # Lists for the dashboard cards and automations
    PerdisSensorDescription(
        key="roster", role="roster",
        value_fn=lambda c: len(c.insights.window(ROSTER_CARD_DAYS)),
        attributes_fn=_roster_attributes,
    ),
    PerdisSensorDescription(
        key="schedule_changes", role="changes", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: len(c.data.recent_changes),
        attributes_fn=_changes_attributes,
    ),
    PerdisSensorDescription(
        key="duty_swaps", role="dutyswap", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: len(c.swaps),
        attributes_fn=_swap_attributes,
    ),
    PerdisSensorDescription(
        key="last_refresh", device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.data.last_success,
        attributes_fn=lambda c: {"online": c.data.online, "last_error": c.data.last_error,
                                 "pages": c.client.discovered_pages},
    ),
)


# Which capability each sensor needs; anything not listed needs the roster, and `last_refresh`
# is a diagnostic that is always created (capability None).
SENSOR_CAPABILITY: dict[str, str | None] = {
    "overtime": CAP_OVERTIME,
    "daily_balance": CAP_DAILY_VALUES,
    "vacation_remaining": CAP_VACATION,
    "weekend_points": CAP_WEEKEND_POINTS,
    "weekend_points_difference": CAP_WEEKEND_AVERAGE,
    "free_weekends_year": CAP_WEEKEND_FREE,
    "duty_swaps": CAP_SWAP,
    "last_refresh": None,
}


def _supported(description: PerdisSensorDescription, capabilities: frozenset[str]) -> bool:
    """True when the portal exposes the data this sensor needs."""
    needed = SENSOR_CAPABILITY.get(description.key, CAP_ROSTER)
    return needed is None or needed in capabilities


async def async_setup_entry(
    hass: HomeAssistant, entry: PerdisConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = coordinator_of(hass, entry)
    async_add_entities(
        PerdisSensor(coordinator, description)
        for description in SENSORS
        if _supported(description, coordinator.capabilities)
    )


class PerdisSensor(PerdisEntity, SensorEntity):
    """A sensor described by a `PerdisSensorDescription`."""

    entity_description: PerdisSensorDescription
    # Long lists belong on the dashboard, not into the recorder database.
    _unrecorded_attributes = frozenset({
        "days", "changes", "recent_entries", "recent", "all_balances", "all", "pages",
        "minutes_until_start", "minutes_until_end",  # change every minute
    })

    @property
    def native_value(self) -> Value:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        description = self.entity_description
        attributes = description.attributes_fn(self.coordinator) if description.attributes_fn else {}
        if description.role:
            attributes = {**attributes, ATTR_ROLE: description.role}
        return attributes or None

