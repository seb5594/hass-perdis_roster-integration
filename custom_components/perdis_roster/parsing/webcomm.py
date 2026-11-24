"""Builds a `Snapshot` from the HTML pages of a classic PERDIS WebComm portal."""

from __future__ import annotations

from collections import defaultdict
from itertools import pairwise
from dataclasses import dataclass, field
from datetime import date, datetime
import re
from zoneinfo import ZoneInfo

from ..models import Balances, Duty, Snapshot, WeekendPointEntry, WeekendPoints
from .calendar import parse_calendar
from .html import innermost_tables, parse_html, table_rows
from .tables import DayRow, key_values, lookup, roster_rows
from .values import (
    classify_duty,
    clock_minutes,
    is_weekday_name,
    line_numbers,
    parse_date,
    parse_duration,
    parse_number,
    shift_times,
    time_ranges,
)

# A pause of at least this long between two parts of a day makes it a split shift.
SPLIT_GAP_MINUTES = 60
MAX_CODE_LENGTH = 12

OVERTIME_LABELS = ("überstunden", "ueberstunden", "mehrarbeit", "arbeitszeitkonto", "zeitkonto", "gleitzeit",
                   "stundenkonto", "plus/minus", "plusminus", "overtime", "overuren", "saldo", "differenz")
TARGET_LABELS = ("sollzeit", "soll", "target", "norm")
ACTUAL_LABELS = ("istzeit", "ist", "actual", "gewerkt")
VACATION_REMAINING_LABELS = ("resturlaub", "urlaub rest", "resturlaubstage", "verbleibender urlaub", "urlaubsrest",
                             "remaining leave", "resterend verlof", "verlofsaldo", "verlof saldo")
VACATION_PLANNED_LABELS = ("geplanter urlaub", "urlaub geplant", "genehmigter urlaub", "verplant", "planned leave",
                           "gepland verlof")
VACATION_ENTITLEMENT_LABELS = ("urlaubsanspruch", "jahresurlaub", "anspruch", "entitlement", "verlofrecht")
POINTS_LABELS = ("we-punkte", "we punkte", "wochenendpunkte", "wochenend-punkte", "punktestand", "weekendpunten",
                 "weekend points", "punkte")
AVERAGE_LABELS = ("durchschnitt", "mittelwert", "gruppenschnitt", "average", "gemiddelde")
FREE_WEEKENDS_LABELS = ("freie wochenenden", "freie we", "free weekends", "vrije weekenden")
EMPLOYEE_ELEMENT = re.compile(r"(lbl(user|name|mitarbeiter|benutzer)|mitarbeitername|username|employee)", re.I)


@dataclass(slots=True)
class WebCommPages:
    """The HTML a WebComm client fetched; missing pages are simply left empty."""

    menu: str = ""
    roster: list[str] = field(default_factory=list)
    balances: str = ""
    vacation: str = ""  # a separate leave-account page (holidays.aspx) when the portal has one
    weekend_points: str = ""


class WebCommParser:
    """Reads duties, accounts and weekend points from WebComm pages."""

    def __init__(self, zone: ZoneInfo) -> None:
        self._zone = zone

    def parse(self, pages: WebCommPages, now: datetime) -> Snapshot:
        today = now.date()
        duties: dict[date, Duty] = {}
        for page in pages.roster:
            for duty in self.parse_roster(page, today):
                duties[duty.day] = duty  # a later page (next month) wins for overlapping days
        # Accounts may live on one page, or split between a time page and a leave page.
        balance_pairs = {
            **key_values(parse_html(pages.balances or pages.menu)),
            **(key_values(parse_html(pages.vacation)) if pages.vacation else {}),
        }
        weekend_document = parse_html(pages.weekend_points or pages.balances or pages.menu)
        return Snapshot(
            fetched_at=now,
            duties=sorted(duties.values(), key=lambda duty: duty.day),
            balances=self.parse_balances(balance_pairs),
            weekend_points=self.parse_weekend_points(weekend_document, today),
            employee_name=self.parse_employee_name(pages.menu),
        )

    # --- Roster ------------------------------------------------------------------------------

    def parse_roster(self, html: str, today: date) -> list[Duty]:
        """Duties of one roster page, read from a data table, or from a calendar as a fallback."""
        document = parse_html(html)
        rows_by_day: dict[date, list[DayRow]] = defaultdict(list)
        for row in roster_rows(document, today):
            rows_by_day[row.day].append(row)
        duties = [duty for day, rows in rows_by_day.items() if (duty := self._duty(day, rows))]
        # WebComm often renders the roster as a month calendar, with each day in a cell tooltip.
        if not duties:
            return parse_calendar(document, self._zone)
        return duties

    def _duty(self, day: date, rows: list[DayRow]) -> Duty | None:
        code = next((row.cells["duty"] for row in rows if row.cells.get("duty")), "") or _loose_code(rows)
        remark = " ".join(row.cells["remark"] for row in rows if row.cells.get("remark")) or None
        segments = sorted(segment for row in rows for segment in _segments(row))
        if not code and not segments and not remark:
            return None
        duty = Duty(day=day, code=code.strip(), remark=remark)
        if segments:
            duty.start, _ = shift_times(day, segments[0][0], segments[0][1], self._zone)
            _, duty.end = shift_times(day, segments[-1][0], segments[-1][1], self._zone)
            duty.split = any(later[0] - earlier[1] >= SPLIT_GAP_MINUTES
                             for earlier, later in pairwise(segments))
        duty.start_location, duty.end_location = _locations(rows, duty.code)
        duty.lines = tuple(dict.fromkeys(line for row in rows for line in line_numbers(row.cells.get("lines", ""))))
        duty.paid_minutes = _sum_durations(row.cells.get("paid") for row in rows)
        duty.break_minutes = _sum_durations(row.cells.get("break") for row in rows)
        duty.duty_type = classify_duty(duty.code, remark or "", duty.has_times)
        return duty

    # --- Accounts ----------------------------------------------------------------------------

    @staticmethod
    def parse_balances(pairs: dict[str, str]) -> Balances:
        def duration(labels: tuple[str, ...], exclude: tuple[str, ...] = ()) -> int | None:
            value = lookup(pairs, labels, exclude)
            return parse_duration(value) if value else None

        def days(labels: tuple[str, ...]) -> float | None:
            value = lookup(pairs, labels)
            return parse_number(value) if value else None

        return Balances(
            overtime_minutes=duration(OVERTIME_LABELS, exclude=("urlaub", "verlof", "leave", "punkte")),
            target_minutes=duration(TARGET_LABELS),
            actual_minutes=duration(ACTUAL_LABELS),
            vacation_remaining_days=days(VACATION_REMAINING_LABELS),
            vacation_planned_days=days(VACATION_PLANNED_LABELS),
            vacation_entitlement_days=days(VACATION_ENTITLEMENT_LABELS),
            raw=pairs,
        )

    @staticmethod
    def parse_weekend_points(document, today: date) -> WeekendPoints:
        pairs = key_values(document)
        points = lookup(pairs, POINTS_LABELS, exclude=("durchschnitt", "average", "gemiddelde"))
        average = lookup(pairs, AVERAGE_LABELS)
        free_weekends = lookup(pairs, FREE_WEEKENDS_LABELS)
        entries = []
        for table in innermost_tables(document):
            for is_header, cells in table_rows(table):
                day = parse_date(cells[0], today) if cells and not is_header else None
                value = parse_number(cells[-1]) if day and len(cells) >= 3 else None
                if day and value is not None:
                    entries.append(WeekendPointEntry(day, cells[1], value))
        return WeekendPoints(
            points=parse_number(points) if points else None,
            group_average=parse_number(average) if average else None,
            free_weekends=_whole_number(free_weekends),
            entries=sorted(entries, key=lambda entry: entry.day),
        )

    @staticmethod
    def parse_employee_name(html: str) -> str | None:
        if not html:
            return None
        element = parse_html(html).find(
            where=lambda e: e.tag not in {"input", "label"} and EMPLOYEE_ELEMENT.search(e.get("id")))
        name = element.text() if element else ""
        return name or None


def _segments(row: DayRow) -> list[tuple[int, int]]:
    """The working periods of a row as operating-day minutes."""
    start, end = clock_minutes(row.cells.get("start", "")), clock_minutes(row.cells.get("end", ""))
    if start is not None and end is not None:
        return [(start, end)]
    text = " | ".join([*row.cells.values(), *row.loose])
    ranges = time_ranges(text)
    if ranges:
        return ranges
    clocks = [minutes for cell in row.loose if (minutes := clock_minutes(cell)) is not None]
    return [(clocks[0], clocks[1])] if len(clocks) >= 2 else []


def _loose_code(rows: list[DayRow]) -> str:
    """The duty code of a table without headers: its first short cell that is not a time."""
    for row in rows:
        for cell in row.loose:
            if (len(cell) <= MAX_CODE_LENGTH and clock_minutes(cell) is None and not time_ranges(cell)
                    and not is_weekday_name(cell)):
                return cell
    return ""


def _locations(rows: list[DayRow], code: str) -> tuple[str | None, str | None]:
    """Start and end place from their columns, or the plain text cells of a table without headers."""
    start = next((row.cells["start_location"] for row in rows if row.cells.get("start_location")), None)
    end = next((row.cells["end_location"] for row in reversed(rows) if row.cells.get("end_location")), None)
    if start is None:
        texts = [cell for row in rows for cell in row.loose if _is_place(cell, code)]
        start = texts[0] if texts else None
        end = end or (texts[-1] if len(texts) > 1 else None)
    return start, end or start


def _is_place(cell: str, code: str) -> bool:
    """A cell of a table without headers that names a place rather than a code, time or weekday."""
    return (cell != code and len(cell) > 2 and any(character.isalpha() for character in cell)
            and clock_minutes(cell) is None and not time_ranges(cell) and not is_weekday_name(cell))


def _whole_number(text: str | None) -> int | None:
    number = parse_number(text) if text else None
    return int(number) if number is not None else None


def _sum_durations(values) -> int | None:
    minutes = [found for value in values if value and (found := parse_duration(value)) is not None]
    return sum(minutes) if minutes else None
