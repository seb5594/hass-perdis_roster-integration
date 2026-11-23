"""Reads the roster when WebComm renders it as an ASP.NET calendar instead of a plain table.

Many WebComm portals show the roster on ``roster.aspx`` as a month calendar. Each day cell is a
``<td>`` with the whole shift packed into its ``title`` tooltip and a link that carries the date,
for example::

    <td class="calDay">
      <a href="...__doPostBack('cal','2026-11-23')"
         title="Dienst: 4711 • Zeit: 05:12 - 13:40 • Anfangsort: Betriebshof • Beschreibung: Früh">
        23
      </a>
    </td>

Days off carry a short code in a ``<span>`` (``U`` for vacation, ``F`` for a free day, ...). This
parser is tolerant: it reads every day cell that has a date and either a time range or an all-day
code, whatever the exact labels of the tooltip are.
"""

from __future__ import annotations

from datetime import date
import re
from zoneinfo import ZoneInfo

from ..models import Duty
from .html import Element
from .values import classify_duty, line_numbers, shift_times, time_ranges

# The tooltip is a list of "Label: value" parts separated by bullets, pipes or line breaks.
TOOLTIP_SEPARATORS = re.compile(r"\s*[•·|▪●•]\s*|\s{2,}|\n")
TOOLTIP_PAIR = re.compile(r"^\s*([^:]{1,40}?)\s*:\s*(.+?)\s*$")
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
GERMAN_DATE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")

# Tooltip labels, grouped by the field they fill. Each list holds the spellings seen in German,
# English and Dutch portals; matching is done on the lower-cased label.
DUTY_LABELS = (
    "dienst",
    "dienstnummer",
    "duty",
    "service",
    "schicht",
    "dienstnr",
)
LOCATION_LABELS = (
    "anfangsort",
    "meldeort",
    "ort",
    "start",
    "von",
    "beginplaats",
    "location",
)
LINE_LABELS = (
    "linie",
    "linien",
    "line",
    "lines",
    "lijn",
)
REMARK_LABELS = (
    "beschreibung",
    "bemerkung",
    "info",
    "description",
    "omschrijving",
    "text",
)


def _tooltip_fields(title: str) -> dict[str, str]:
    """The ``Label: value`` pairs of a tooltip, keyed by the lower-cased label."""
    fields: dict[str, str] = {}
    for part in TOOLTIP_SEPARATORS.split(title):
        pair = TOOLTIP_PAIR.match(part)
        if pair:
            fields.setdefault(pair.group(1).strip().lower(), pair.group(2).strip())
    return fields


def _pick(fields: dict[str, str], labels: tuple[str, ...]) -> str:
    """The value of the first label present in the tooltip."""
    return next((fields[label] for label in labels if fields.get(label)), "")


def _cell_title(cell: Element) -> str:
    """The tooltip of a day: ASP.NET puts it on the cell or on the day link inside it."""
    if cell.get("title"):
        return cell.get("title")
    return next((link.get("title") for link in cell.find_all("a") if link.get("title")), "")


def _cell_date(cell: Element) -> date | None:
    """The calendar day a cell stands for, taken from a link or a date in its text or tooltip."""
    haystacks = [_cell_title(cell)]
    haystacks += [link.get("href") for link in cell.find_all("a")]
    haystacks += [cell.text()]
    for text in haystacks:
        iso = ISO_DATE.search(text)
        if iso:
            return _safe_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        german = GERMAN_DATE.search(text)
        if german:
            return _safe_date(int(german.group(3)), int(german.group(2)), int(german.group(1)))
    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _day_cells(document: Element) -> list[Element]:
    """Table cells that carry a date and a tooltip or a code span: the days of a roster calendar."""
    return [
        cell
        for cell in document.find_all("td")
        if (_cell_title(cell) or cell.find("span") is not None) and _cell_date(cell) is not None
    ]


def parse_calendar(document: Element, zone: ZoneInfo) -> list[Duty]:
    """Every duty of a calendar-rendered roster page."""
    duties: dict[date, Duty] = {}
    for cell in _day_cells(document):
        day = _cell_date(cell)
        if day is None or day in duties:
            continue
        duty = _duty_from_cell(cell, day, zone)
        if duty is not None:
            duties[day] = duty
    return sorted(duties.values(), key=lambda duty: duty.day)


def _duty_from_cell(cell: Element, day: date, zone: ZoneInfo) -> Duty | None:
    title = _cell_title(cell)
    fields = _tooltip_fields(title)
    ranges = time_ranges(title)
    code_span = cell.find("span")
    span_code = code_span.text().strip() if code_span else ""

    if ranges:  # a working shift with a start and an end
        code = _pick(fields, DUTY_LABELS) or span_code or _non_numeric_text(cell)
        start, end = shift_times(day, ranges[0][0], ranges[-1][1], zone)
        remark = _pick(fields, REMARK_LABELS) or None
        duty = Duty(day=day, code=code.strip(), start=start, end=end, remark=remark)
        duty.start_location = _pick(fields, LOCATION_LABELS) or None
        duty.end_location = duty.start_location
        duty.lines = tuple(line_numbers(_pick(fields, LINE_LABELS)))
        duty.split = len(ranges) > 1
        duty.duty_type = classify_duty(duty.code, remark or "", has_times=True)
        return duty

    # An all-day entry: a day off, vacation, training, ... named by a short code and/or the title.
    code = span_code or _pick(fields, DUTY_LABELS)
    remark = title.strip() or None
    if not code and not remark:
        return None
    duty = Duty(day=day, code=code.strip(), remark=remark)
    duty.duty_type = classify_duty(duty.code, remark or "", has_times=False)
    return duty


def _non_numeric_text(cell: Element) -> str:
    """The visible cell text unless it is only the day number; a last-resort duty label."""
    text = cell.text().strip()
    return "" if text.isdigit() else text
