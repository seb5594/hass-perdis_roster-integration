"""Reads the roster when WebComm renders it as a month calendar instead of a plain table.

Two calendar styles exist:

* Some portals pack the whole shift into each day cell's ``title`` tooltip
  (``Dienst: 4711 • Zeit: 05:12 - 13:40 • ...``).
* Others show only the duty number or a code in the cell (``FREI``, ``3095``, ``SF Neu``) and keep
  the times on the shift's own detail page. The real times are then fetched separately (see
  ``shift_detail.py``) and merged in.

This parser reads both: it finds every day cell, takes its date (from a link, the text or the
month that was fetched) and either the timed shift from the tooltip or just the code.
"""

from __future__ import annotations

from datetime import date, timedelta
import re
from zoneinfo import ZoneInfo

from ..models import Duty
from .html import Element
from .values import classify_duty, is_weekday_name, line_numbers, parse_duration, shift_times, time_ranges

# The tooltip is a run of "Label: value" fields. Portals separate and pad them differently: a single
# bullet ("Dienst: 4711 • Zeit: ..."), or a label whose value sits after one or two bullets
# ("Anfangsort:  •  • Hbf"). This reads a field's value as everything up to the next bullet, pipe or
# line break, after skipping the bullets a portal may insert between the label and its value.
TOOLTIP_FIELD = re.compile(r"([^:•·|\n]{2,40}?)\s*:\s*[•·\s]*([^•·|\n]+?)\s*(?=[•·|\n]|$)")
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
GERMAN_DATE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
DAY_NUMBER = re.compile(r"\b([0-3]?\d)\b")

# Month names (German, English, Dutch) to date a calendar from its heading, e.g. "November 2026".
MONTH_NAMES: dict[str, int] = {
    name: number
    for number, names in enumerate(
        (
            ("januar", "january", "januari", "jan"),
            ("februar", "february", "februari", "feb"),
            ("märz", "maerz", "march", "maart", "mar", "mrz"),
            ("april", "apr"),
            ("mai", "may", "mei"),
            ("juni", "june", "jun"),
            ("juli", "july", "jul"),
            ("august", "augustus", "aug"),
            ("september", "sep", "sept"),
            ("oktober", "october", "okt", "oct"),
            ("november", "nov"),
            ("dezember", "december", "dez", "dec"),
        ),
        start=1,
    )
    for name in names
}
MONTH_HEADING = re.compile(r"([A-Za-zÄÖÜäöü]{3,9})\.?\s+(\d{4})")

# Tooltip labels, grouped by the field they fill.
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
PAID_LABELS = (
    "lohnstunden",
    "bezahlt",
    "bezahlte zeit",
    "paid",
    "paid hours",
    "loonuren",
)


def _tooltip_fields(title: str) -> dict[str, str]:
    """The ``Label: value`` pairs of a tooltip, keyed by the lower-cased label."""
    fields: dict[str, str] = {}
    for label, value in TOOLTIP_FIELD.findall(title):
        fields.setdefault(label.strip().lower(), value.strip())
    return fields


def _pick(fields: dict[str, str], labels: tuple[str, ...]) -> str:
    return next((fields[label] for label in labels if fields.get(label)), "")


def _cell_title(cell: Element) -> str:
    """The tooltip of a day: ASP.NET puts it on the cell or on the day link inside it."""
    if cell.get("title"):
        return cell.get("title")
    return next((link.get("title") for link in cell.find_all("a") if link.get("title")), "")


def _cell_hrefs(cell: Element) -> list[str]:
    """Every link target on the cell or an element inside it, e.g. ``roster.aspx?2026-11-24``."""
    carriers = [cell, *cell.find_all({"a", "span", "strong"})]
    return [href for element in carriers if (href := element.get("href"))]


def _cell_date(cell: Element) -> date | None:
    """A full date carried by the cell: in a link target, its text or its tooltip. None when absent."""
    haystacks = [_cell_title(cell), *_cell_hrefs(cell), cell.text()]
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


def _day_number(cell: Element) -> int | None:
    """The day-of-month a cell is headed with (the big number in a calendar cell)."""
    found = DAY_NUMBER.search(cell.text())
    if not found:
        return None
    number = int(found.group(1))
    return number if 1 <= number <= 31 else None


def _cell_code(cell: Element, day_number: int | None) -> str:
    """The duty code shown in a day cell, without the day number and any date."""
    text = cell.text()
    text = ISO_DATE.sub(" ", GERMAN_DATE.sub(" ", text))
    if day_number is not None:
        text = re.sub(rf"\b0?{day_number}\b", " ", text, count=1)
    return re.sub(r"\s{2,}", " ", text).strip()


def _is_day_cell(cell: Element) -> bool:
    """A calendar day cell: it has a day number and either a tooltip, a code span or a code text.

    The faded cells of the neighbouring months carry only a day number (no shift and no absence),
    so they produce no duty and need no special casing here.
    """
    number = _day_number(cell)
    if number is None or is_weekday_name(cell.text()):
        return False
    return bool(_cell_title(cell) or cell.find("span") is not None or _cell_code(cell, number))


def parse_calendar(document: Element, zone: ZoneInfo, month: date | None = None) -> list[Duty]:
    """Every duty of a calendar-rendered roster page.

    `month` is the first of the month the page was fetched for; it dates the cells of portals whose
    calendar carries only day numbers, not full dates.
    """
    cells = [cell for cell in document.find_all("td") if _is_day_cell(cell)]
    dated = [(cell, _cell_date(cell)) for cell in cells]
    month = month or detect_month(document)
    if any(day for _, day in dated):
        # A single cell without its own date (ASP.NET often renders the day next to the selected one
        # without a date link) must not drop that day: fill it from its dated neighbours.
        pairs = _fill_missing_dates(dated)
    elif month is not None:
        pairs = _dates_from_month(cells, month)
    else:
        return []

    duties: dict[date, Duty] = {}
    for cell, day in pairs:
        if day in duties:
            continue
        duty = _duty_from_cell(cell, day, zone)
        if duty is not None:
            duties[day] = duty
    return sorted(duties.values(), key=lambda duty: duty.day)


def _fill_missing_dates(dated: list[tuple[Element, date | None]]) -> list[tuple[Element, date]]:
    """Date every content cell, inferring an undated one from the nearest dated neighbour.

    The calendar grid is chronological, so a cell's date is a dated neighbour's date shifted by the
    difference of their day numbers. The ``day == number`` check keeps a faded adjacent-month cell
    from being mis-dated into the shown month.
    """
    resolved: list[list] = [[cell, day] for cell, day in dated]
    for index, entry in enumerate(resolved):
        if entry[1] is not None:
            continue
        number = _day_number(entry[0])
        if number is None:
            continue
        anchor = _nearest_dated(resolved, index)
        if anchor is None:
            continue
        anchor_number = _day_number(anchor[0])
        if anchor_number is None:
            continue
        candidate = anchor[1] + timedelta(days=number - anchor_number)
        if candidate.day == number:
            entry[1] = candidate
    return [(cell, day) for cell, day in resolved if day is not None]


def _nearest_dated(resolved: list[list], index: int) -> list | None:
    """The dated cell closest to `index` in document (chronological) order."""
    for offset in range(1, len(resolved)):
        for neighbour in (index - offset, index + offset):
            if 0 <= neighbour < len(resolved) and resolved[neighbour][1] is not None:
                return resolved[neighbour]
    return None


def detect_month(document: Element) -> date | None:
    """The month a calendar page is for, read from a heading like "Dienstplan November 2026"."""
    for match in MONTH_HEADING.finditer(document.text()):
        number = MONTH_NAMES.get(match.group(1).lower())
        if number is not None:
            return date(int(match.group(2)), number, 1)
    return None


def _dates_from_month(cells: list[Element], month: date) -> list[tuple[Element, date]]:
    """Map the day-number cells of one month to dates, ignoring the adjacent-month cells.

    The target month's days form the single ascending run 1, 2, ... N in document order; the faded
    leading (previous month) and trailing (next month) cells are outside that run and are skipped.
    """
    first_of_next = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    last_day = (first_of_next - timedelta(days=1)).day
    pairs: list[tuple[Element, date]] = []
    expected = 1
    for cell in cells:
        number = _day_number(cell)
        if number == expected and expected <= last_day:
            pairs.append((cell, date(month.year, month.month, expected)))
            expected += 1
        elif expected > last_day:
            break
    return pairs


def _duty_from_cell(cell: Element, day: date, zone: ZoneInfo) -> Duty | None:
    title = _cell_title(cell)
    fields = _tooltip_fields(title)
    # The start and end come from the tooltip's time ranges ("10:22 - 18:03"); a duration such as
    # "Dienstdauer: 08:15" is a single time, not a range, so it is never mistaken for them.
    ranges = time_ranges(title)
    # The code is the tooltip's duty field, otherwise the cell text without the day number (which
    # may sit in its own span) and without any date.
    code = _pick(fields, DUTY_LABELS) or _cell_code(cell, _day_number(cell))

    if ranges:  # a working shift with a start and an end in the tooltip
        start, end = shift_times(day, ranges[0][0], ranges[-1][1], zone)
        remark = _pick(fields, REMARK_LABELS) or None
        duty = Duty(day=day, code=code.strip(), start=start, end=end, remark=remark)
        duty.start_location = _pick(fields, LOCATION_LABELS) or None
        duty.end_location = duty.start_location
        duty.lines = tuple(line_numbers(_pick(fields, LINE_LABELS)))
        duty.paid_minutes = parse_duration(_pick(fields, PAID_LABELS)) or None
        duty.split = len(ranges) > 1
        duty.duty_type = classify_duty(duty.code, remark or "", has_times=True)
        return duty

    # Only a code: a day off, an absence or a shift whose times live on its detail page.
    remark = title.strip() or None
    if not code and not remark:
        return None
    duty = Duty(day=day, code=code.strip(), remark=remark)
    duty.duty_type = classify_duty(duty.code, remark or "", has_times=False)
    return duty
