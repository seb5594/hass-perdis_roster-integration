"""A calendar with every duty and day off, for the calendar dashboard and calendar triggers."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .capabilities import CAP_ROSTER
from .coordinator import PerdisConfigEntry, PerdisCoordinator
from .entity import PerdisEntity
from .models import Duty, DutyType

CALENDAR = EntityDescription(key="duties")

# Calendar entries are plain text; these keep them readable in both languages.
DAY_LABELS = {
    "en": {DutyType.FREE: "Day off", DutyType.VACATION: "Vacation", DutyType.SICK: "Sick leave",
           DutyType.COMPENSATION: "Time off in lieu", DutyType.TRAINING: "Training", DutyType.RESERVE: "Reserve",
           DutyType.WORK: "Duty", DutyType.UNKNOWN: "Roster"},
    "de": {DutyType.FREE: "Frei", DutyType.VACATION: "Urlaub", DutyType.SICK: "Krank",
           DutyType.COMPENSATION: "Freizeitausgleich", DutyType.TRAINING: "Schulung", DutyType.RESERVE: "Bereitschaft",
           DutyType.WORK: "Dienst", DutyType.UNKNOWN: "Dienstplan"},
}
DETAIL_LABELS = {
    "en": {"start": "Starts at", "end": "Ends at", "lines": "Lines", "hours": "Paid hours", "split": "Split shift"},
    "de": {"start": "Beginn in", "end": "Ende in", "lines": "Linien", "hours": "Bezahlte Stunden",
           "split": "Geteilter Dienst"},
}


async def async_setup_entry(
    hass: HomeAssistant, entry: PerdisConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if CAP_ROSTER in coordinator.capabilities:
        async_add_entities([PerdisCalendar(coordinator, CALENDAR)])


class PerdisCalendar(PerdisEntity, CalendarEntity):
    """Shifts as timed events, days off and absences as all-day events."""

    # Home Assistant 2026.9 reads the calendar's initial colour from the entity: declare it here,
    # so it is not looked up on the shared (colourless) entity description. Harmless on older cores.
    _attr_initial_color = None

    def __init__(self, coordinator: PerdisCoordinator, description: EntityDescription) -> None:
        super().__init__(coordinator, description)
        language = (coordinator.hass.config.language or "en").split("-")[0]
        self._days = DAY_LABELS.get(language, DAY_LABELS["en"])
        self._details = DETAIL_LABELS.get(language, DETAIL_LABELS["en"])

    @property
    def event(self) -> CalendarEvent | None:
        """The running or next shift; on a day off without shifts ahead, the day itself."""
        insights = self.coordinator.insights
        duty = insights.next_shift or insights.today_duty
        return self._event(duty) if duty else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        events = (self._event(duty) for duty in self.coordinator.insights.duties)
        return [event for event in events if _overlaps(event, start_date, end_date)]

    def _event(self, duty: Duty) -> CalendarEvent:
        if duty.has_times:
            title = f"{self._days[duty.duty_type]} {duty.code}".strip()
            if duty.lines:
                title += f" · {', '.join(duty.lines)}"
            return CalendarEvent(start=duty.start, end=duty.end, summary=title, location=duty.start_location,
                                 description=self._description(duty), uid=f"perdis-{duty.day.isoformat()}")
        label = self._days[duty.duty_type]
        if duty.code and duty.code.upper() != label.upper():
            label = f"{label} ({duty.code})"
        return CalendarEvent(start=duty.day, end=duty.day + timedelta(days=1), summary=label,
                             description=duty.remark, uid=f"perdis-{duty.day.isoformat()}")

    def _description(self, duty: Duty) -> str:
        words = self._details
        moves_on = duty.end_location and duty.end_location != duty.start_location
        lines = [
            f"{words['start']}: {duty.start_location}" if duty.start_location else None,
            f"{words['end']}: {duty.end_location}" if moves_on else None,
            f"{words['lines']}: {', '.join(duty.lines)}" if duty.lines else None,
            f"{words['hours']}: {duty.worked_minutes / 60:.2f}" if duty.worked_minutes else None,
            words["split"] if duty.split else None,
            duty.remark,
        ]
        return "\n".join(line for line in lines if line)


def _overlaps(event: CalendarEvent, start: datetime, end: datetime) -> bool:
    event_start, event_end = event.start, event.end
    if not isinstance(event_start, datetime):
        event_start = dt_util.start_of_local_day(event_start)
        event_end = dt_util.start_of_local_day(event_end)
    return event_start < end and event_end > start
