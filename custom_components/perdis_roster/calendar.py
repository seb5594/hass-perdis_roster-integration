"""A calendar with every duty and day off, for the calendar dashboard and calendar triggers."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .capabilities import CAP_ROSTER
from .const import CONF_CALENDAR_LEG_EVENTS, DEFAULT_CALENDAR_LEG_EVENTS
from .coordinator import PerdisConfigEntry, PerdisCoordinator, coordinator_of
from .entity import ATTR_ROLE, PerdisEntity
from .labels import duty_type_labels
from .models import Duty, DutyType

CALENDAR = EntityDescription(key="duties")

# Calendar entries are plain text; these keep them readable in both languages.
DETAIL_LABELS = {
    "en": {"start": "Starts at", "hours": "Paid hours", "split": "Split shift", "parts": "Legs",
           "line": "Line", "course": "Course", "break": "Break"},
    "de": {"start": "Beginn in", "hours": "Bezahlte Stunden", "split": "Geteilter Dienst",
           "parts": "Abschnitte", "line": "Linie", "course": "Kurs", "break": "Pause"},
}


async def async_setup_entry(
    hass: HomeAssistant, entry: PerdisConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = coordinator_of(hass, entry)
    if CAP_ROSTER in coordinator.capabilities:
        async_add_entities([PerdisCalendar(coordinator, CALENDAR)])


class PerdisCalendar(PerdisEntity, CalendarEntity):
    """Shifts as timed events, days off and absences as all-day events."""

    # Home Assistant 2026.9 reads the calendar's initial colour from the entity: declare it here,
    # so it is not looked up on the shared (colourless) entity description. Harmless on older cores.
    _attr_initial_color = None
    # Lets the dashboard cards find this calendar by its role, like the sensors, so a calendar card
    # needs no hand-typed entity id.
    _attr_extra_state_attributes = {ATTR_ROLE: "calendar"}

    def __init__(self, coordinator: PerdisCoordinator, description: EntityDescription) -> None:
        super().__init__(coordinator, description)
        language = coordinator.hass.config.language or "en"
        self._days = duty_type_labels(language)
        self._details = DETAIL_LABELS.get(language.split("-")[0], DETAIL_LABELS["en"])

    @property
    def event(self) -> CalendarEvent | None:
        """The running or next shift; on a day off without shifts ahead, the day itself."""
        insights = self.coordinator.insights
        duty = insights.next_shift or insights.today_duty
        return self._event(duty) if duty else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        # Optionally break a shift into one event per leg, so a day reads as a structured timeline
        # instead of a single block with the legs hidden in the description.
        split = self.coordinator.option(CONF_CALENDAR_LEG_EVENTS, DEFAULT_CALENDAR_LEG_EVENTS)
        events: list[CalendarEvent] = []
        for duty in self.coordinator.insights.duties:
            if not _worth_showing(duty):
                continue
            if split and duty.is_working and duty.segments:
                events.extend(self._leg_events(duty))
            else:
                events.append(self._event(duty))
        return [event for event in events if _overlaps(event, start_date, end_date)]

    def _leg_events(self, duty: Duty) -> list[CalendarEvent]:
        """Each leg of a shift as its own event: a drive by its line and course, a break as a break."""
        events = []
        for index, segment in enumerate(_merge_breaks(duty.segments)):
            events.append(CalendarEvent(
                start=segment.start, end=segment.end,
                summary=self._leg_title(duty, segment),
                location=self._leg_place(segment),
                description=_relief(segment.relief),
                uid=f"perdis-{duty.day.isoformat()}-{index}"))
        return events

    def _leg_title(self, duty: Duty, segment) -> str:
        if segment.is_break:
            return self._details["break"]
        parts = [
            f"{self._details['line']} {segment.line}" if segment.line else "",
            f"{self._details['course']} {segment.course}" if segment.course else "",
        ]
        title = " · ".join(part for part in parts if part)
        # A preparation or wrap-up leg carries no line; fall back to the duty number.
        return title or f"{self._days[DutyType.WORK]} {duty.code}".strip()

    def _leg_place(self, segment) -> str | None:
        start, end = segment.start_location or "", segment.end_location or ""
        if end and end != start:
            return f"{start} → {end}".strip()
        return start or None

    def _event(self, duty: Duty) -> CalendarEvent:
        label = self._title(duty)
        # The duty number and lines only mean something for a working shift; an absence (sick, day
        # off, vacation) reads as just its name, so "Krank k" or "Frei (R)" become plain "Krank".
        if duty.has_times:
            title = label
            if duty.is_working:
                title = f"{label} {duty.code}".strip()
                if duty.lines:
                    title += f" · {', '.join(duty.lines)}"
            return CalendarEvent(start=duty.start, end=duty.end, summary=title, location=duty.start_location,
                                 description=self._description(duty), uid=f"perdis-{duty.day.isoformat()}")
        if duty.is_working and duty.code and duty.code.upper() != label.upper():
            label = f"{label} ({duty.code})"
        return CalendarEvent(start=duty.day, end=duty.day + timedelta(days=1), summary=label,
                             description=duty.remark, uid=f"perdis-{duty.day.isoformat()}")

    def _title(self, duty: Duty) -> str:
        """The duty-type name, except for an unrecognised entry, which shows its own code.

        "Krank"/"Frei" read better than "Krank (k)"; but an unknown code like "SF Neu" carries the
        only information there is, so the generic "roster" label would hide it.
        """
        if duty.duty_type is DutyType.UNKNOWN and duty.code:
            return duty.code
        return self._days[duty.duty_type]

    def _description(self, duty: Duty) -> str:
        words = self._details
        header = [
            f"{words['hours']}: {duty.worked_minutes / 60:.2f}" if duty.worked_minutes else None,
            words["split"] if duty.split else None,
            duty.remark,
        ]
        lines = [line for line in header if line]
        if duty.segments:
            lines.append(f"{words['parts']}:")
            lines.extend(self._segment_line(segment) for segment in _merge_breaks(duty.segments))
        elif duty.start_location:  # a timed duty whose detail legs are not (yet) available
            lines.insert(0, f"{words['start']}: {duty.start_location}")
        return "\n".join(lines)

    def _segment_line(self, segment) -> str:
        """One leg of the shift: the relief place and time first, then the line, course and, in
        parentheses, the relief direction, e.g. 'Hbf 10:32-14:32 · Line 21 · Course 11 (+/-)'.
        """
        where = segment.start_location or ""
        head = f"{where} {segment.start:%H:%M}-{segment.end:%H:%M}".strip()
        if segment.is_break:
            minutes = max(round((segment.end - segment.start).total_seconds() / 60), 0)
            return f"{head} · {self._details['break']} {minutes} min"
        details = " · ".join(part for part in (
            f"{self._details['line']} {segment.line}" if segment.line else "",
            f"{self._details['course']} {segment.course}" if segment.course else "",
        ) if part)
        relief = f" ({_relief(segment.relief)})" if segment.relief else ""
        return f"{head}{(' · ' + details) if details else ''}{relief}"


def _relief(marker: str | None) -> str:
    """A relief marker spaced out for legibility: "+/+" -> "+ / +"."""
    return (marker or "").replace(" ", "").replace("/", " / ")


def _merge_breaks(segments: list) -> list:
    """Collapse a run of back-to-back breaks into one, so three short breaks read as one block."""
    merged: list = []
    for segment in segments:
        if segment.is_break and merged and merged[-1].is_break:
            merged[-1] = replace(merged[-1], end=segment.end,
                                 end_location=segment.end_location or merged[-1].end_location)
        else:
            merged.append(segment)
    return merged


def _worth_showing(duty: Duty) -> bool:
    """Skip only an empty parser artefact: an unknown day with no code, no times and no remark.

    A day the portal marks without a duty number but with a note ("no information for this day
    yet") still carries that remark, so it stays on the calendar — today included.
    """
    return (duty.duty_type is not DutyType.UNKNOWN or bool(duty.code) or duty.has_times
            or bool(duty.remark))


def _overlaps(event: CalendarEvent, start: datetime, end: datetime) -> bool:
    event_start, event_end = event.start, event.end
    if not isinstance(event_start, datetime):
        event_start = dt_util.start_of_local_day(event_start)
        event_end = dt_util.start_of_local_day(event_end)
    return event_start < end and event_end > start
