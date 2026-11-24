"""Reads the detail page of one shift and turns it into real times, places, lines and segments.

The month roster only shows a duty number per day. The actual working times live on the shift's
own page (``shift.aspx?YYYY-MM-DD``, titled "Tätigkeiten und Abwesenheiten am ..."), a table with
one row per leg of the shift:

    Dienst | Von | Ort | Bis | Ort | Abw. | Linie | Kurs | Umlauf | Tätig.-Art / Beschr.

Each leg is a drive, a break, a preparation or a transition. From these rows the real shift start
and end, the reporting points, the lines and a breakdown of the shift are derived.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from zoneinfo import ZoneInfo

from ..models import Duty, DutySegment
from .html import Element, innermost_tables, parse_html, table_rows
from .values import clock_minutes, line_numbers, normalize_label, operating_time

# Column headers, by the field they fill. The from/to places are the "Ort" columns that follow the
# "Von" and "Bis" time columns, so they are located relative to those, not by name.
TIME_FROM_LABELS = ("von", "from", "beginn", "van")
TIME_TO_LABELS = ("bis", "to", "ende", "tot")
PLACE_LABELS = ("ort", "location", "plaats")
LINE_LABELS = ("linie", "line", "lijn")
KIND_LABELS = ("art", "beschr", "tätig", "taetig", "beschreibung", "description")

# Leg kinds that do not count as paid working time: unpaid breaks and transitions between duty
# parts. Everything else (driving, preparation, wrap-up, turnarounds) counts as worked.
BREAK_KINDS = ("üz", "ue z", "uez", "pause", "unbezahlt", "break", "pauze")
SPLIT_GAP_MINUTES = 60


@dataclass(slots=True)
class ShiftDetail:
    """The legs of one shift and the figures derived from them."""

    segments: list[DutySegment] = field(default_factory=list)

    @property
    def has_times(self) -> bool:
        return bool(self.segments)

    def apply_to(self, duty: Duty) -> None:
        """Enrich a roster duty with the real times, places, lines and legs of its detail page."""
        if not self.segments:
            return
        duty.start = self.segments[0].start
        duty.end = self.segments[-1].end
        duty.start_location = self.segments[0].start_location or duty.start_location
        duty.end_location = self.segments[-1].end_location or duty.end_location
        lines = [segment.line for segment in self.segments if segment.line]
        duty.lines = tuple(dict.fromkeys(line for part in lines for line in line_numbers(part))) or duty.lines
        duty.break_minutes = sum(_minutes(s) for s in self.segments if s.is_break) or None
        duty.paid_minutes = sum(_minutes(s) for s in self.segments if not s.is_break) or None
        duty.split = any(
            (later.start - earlier.end).total_seconds() // 60 >= SPLIT_GAP_MINUTES
            for earlier, later in zip(self.segments, self.segments[1:], strict=False)
            if not earlier.is_break and not later.is_break
        )
        duty.segments = self.segments


def _minutes(segment: DutySegment) -> int:
    return max(int((segment.end - segment.start).total_seconds() // 60), 0)


def parse_shift_detail(html: str, day: date, zone: ZoneInfo) -> ShiftDetail:
    """The legs of the shift on `day`, read from its detail page."""
    document = parse_html(html)
    table = _detail_table(document)
    if table is None:
        return ShiftDetail()
    rows = table_rows(table)
    columns = _columns(rows)
    if "from" not in columns or "to" not in columns:
        return ShiftDetail()
    segments: list[DutySegment] = []
    for is_header, cells in rows:
        if is_header:
            continue
        segment = _segment(cells, columns, day, zone)
        if segment is not None:
            segments.append(segment)
        elif segments and (relief := _relief_marker(cells, columns)):
            # A row without times that only carries a "+/-" marker: the relief direction of the leg
            # just above it (take a vehicle over at the start / hand it over at the end).
            segments[-1].relief = relief
    segments.sort(key=lambda segment: segment.start)
    return ShiftDetail(segments)


def _relief_marker(cells: list[str], columns: dict[str, int]) -> str:
    """A relief marker like "+/-" from a row's description cell, or "" when it is something else."""
    text = _cell(cells, columns.get("kind"))
    compact = text.replace(" ", "")
    return text.strip() if compact and "/" in compact and set(compact) <= set("+-–/") else ""


def _detail_table(document: Element) -> Element | None:
    """The innermost table whose header has a "from" and a "to" time column."""
    for table in innermost_tables(document):
        for is_header, cells in table_rows(table):
            labels = [normalize_label(cell) for cell in cells]
            if (is_header or _looks_like_header(labels)) and _has(labels, TIME_FROM_LABELS) \
                    and _has(labels, TIME_TO_LABELS):
                return table
    return None


def _looks_like_header(labels: list[str]) -> bool:
    return _has(labels, TIME_FROM_LABELS) and _has(labels, TIME_TO_LABELS) and not any(
        clock_minutes(label) is not None for label in labels
    )


def _has(labels: list[str], wanted: tuple[str, ...]) -> bool:
    return any(any(word in label for word in wanted) for label in labels)


def _columns(rows: list[tuple[bool, list[str]]]) -> dict[str, int]:
    """Map from field name to column index, read from the first header-like row."""
    for is_header, cells in rows:
        labels = [normalize_label(cell) for cell in cells]
        if not (is_header or _looks_like_header(labels)):
            continue
        columns: dict[str, int] = {}
        for index, label in enumerate(labels):
            if "from" not in columns and any(word == label or word in label for word in TIME_FROM_LABELS):
                columns["from"] = index
            elif "to" not in columns and any(word == label or word in label for word in TIME_TO_LABELS):
                columns["to"] = index
            elif any(word in label for word in LINE_LABELS):
                columns.setdefault("line", index)
            elif any(word in label for word in KIND_LABELS):
                columns["kind"] = index
        # The two "Ort" columns sit right after the "Von" and "Bis" time columns.
        places = [index for index, label in enumerate(labels) if any(word in label for word in PLACE_LABELS)]
        columns["from_place"] = next((p for p in places if p > columns.get("from", -1)), None)
        columns["to_place"] = next((p for p in places if p > columns.get("to", -1)), None)
        return {key: value for key, value in columns.items() if value is not None}
    return {}


def _segment(cells: list[str], columns: dict[str, int], day: date, zone: ZoneInfo) -> DutySegment | None:
    start_minutes = _cell_minutes(cells, columns.get("from"))
    end_minutes = _cell_minutes(cells, columns.get("to"))
    if start_minutes is None or end_minutes is None:
        return None
    if end_minutes < start_minutes:  # a leg that runs over midnight
        end_minutes += 24 * 60
    kind = _cell(cells, columns.get("kind"))
    return DutySegment(
        start=operating_time(day, start_minutes, zone),
        end=operating_time(day, end_minutes, zone),
        start_location=_cell(cells, columns.get("from_place")) or None,
        end_location=_cell(cells, columns.get("to_place")) or None,
        line=_cell(cells, columns.get("line")) or None,
        kind=kind,
        is_break=any(word in kind.lower() for word in BREAK_KINDS),
    )


def _cell(cells: list[str], index: int | None) -> str:
    return cells[index].strip() if index is not None and index < len(cells) else ""


def _cell_minutes(cells: list[str], index: int | None) -> int | None:
    return clock_minutes(_cell(cells, index))
