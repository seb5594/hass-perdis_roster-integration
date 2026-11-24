"""Reads the duty-swap page: the open swap offers and the period the portal accepts requests for.

The swap page (``dutyswap.aspx``) lists every open swap in a table and, in its heading, the date
range a driver may enter new swap requests for. The portal is undocumented, so the table is read by
its column headers rather than by fixed positions, which keeps it working across operators and
languages. Each row carries a radio button whose id is the handle the portal uses to accept, reject
or withdraw that swap; it is kept so an action can refer back to the exact entry.
"""

from __future__ import annotations

from datetime import date
import re

from ..models import DutySwap
from .html import Element, parse_html
from .tables import innermost_tables, table_rows
from .values import normalize_label, parse_date

# Column headers, by the field they fill (German, English, Dutch).
COLUMN_LABELS: dict[str, tuple[str, ...]] = {
    "from": ("von", "from", "datum von", "van", "ab"),
    "to": ("bis", "to", "tot"),
    "partner": ("tauschpartner", "partner", "kollege", "collega", "mit"),
    "duty": ("dienst", "duty", "service", "schicht"),
    "time": ("zeit", "time", "tijd", "uhrzeit"),
    "status": ("status", "stand", "zustand"),
    "type": ("typ", "type", "art"),
}
# Two dates in the heading "... für den Zeitraum vom 25.11.2026 bis 09.12.2026 ...".
WINDOW_DATES = re.compile(
    r"(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{4}-\d{2}-\d{2}).{0,12}?"
    r"(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{4}-\d{2}-\d{2})"
)


def parse_swap_window(html: str, today: date) -> tuple[date, date] | None:
    """The period new swap requests may be entered for, read from the page heading."""
    return _window_from_text(parse_html(html).text(), today)


def _window_from_text(text: str, today: date) -> tuple[date, date] | None:
    match = WINDOW_DATES.search(text)
    if not match:
        return None
    start, end = parse_date(match.group(1), today), parse_date(match.group(2), today)
    return (start, end) if start and end and start <= end else None


def parse_duty_swaps(html: str, today: date) -> list[DutySwap]:
    """Every open swap offer on the duty-swap page; the empty placeholder row is left out."""
    document = parse_html(html)
    table = _swap_table(document)
    if table is None:
        return []
    columns = _columns(table)
    swaps: list[DutySwap] = []
    for row in _data_rows(table):
        swap = _swap_from_row(row, columns, today)
        if swap is not None:
            swaps.append(swap)
    return swaps


def _swap_table(document: Element) -> Element | None:
    """The table whose header names a swap partner and a duty."""
    for table in innermost_tables(document):
        header = next((cells for is_header, cells in table_rows(table) if is_header), [])
        labels = [normalize_label(cell) for cell in header]
        if _column_index(labels, COLUMN_LABELS["partner"]) is not None \
                and _column_index(labels, COLUMN_LABELS["duty"]) is not None:
            return table
    return None


def _columns(table: Element) -> dict[str, int]:
    header = next((cells for is_header, cells in table_rows(table) if is_header), [])
    labels = [normalize_label(cell) for cell in header]
    return {field: index for field in COLUMN_LABELS
            if (index := _column_index(labels, COLUMN_LABELS[field])) is not None}


def _column_index(labels: list[str], wanted: tuple[str, ...]) -> int | None:
    return next((index for index, label in enumerate(labels)
                 if any(word == label or word in label.split() for word in wanted)), None)


def _data_rows(table: Element) -> list[Element]:
    return [row for row in table.find_all("tr", lambda tr: tr.ancestor("table") is table)
            if not _is_header_row(row)]


def _is_header_row(row: Element) -> bool:
    cells = _cells(row)
    return bool(cells) and all(cell.tag == "th" for cell in cells)


def _cells(row: Element) -> list[Element]:
    return [cell for cell in row.children if isinstance(cell, Element) and cell.tag in {"td", "th"}]


def _swap_from_row(row: Element, columns: dict[str, int], today: date) -> DutySwap | None:
    cells = _cells(row)
    texts = [cell.text().strip() for cell in cells]
    if not any(text and text != "-" for text in texts):  # the empty placeholder row
        return None
    swap_id = _radio_id(row)
    if not swap_id:
        return None

    def value(field: str) -> str:
        index = columns.get(field)
        return texts[index] if index is not None and index < len(texts) else ""

    return DutySwap(
        swap_id=swap_id,
        day=parse_date(value("from"), today),
        end_day=parse_date(value("to"), today),
        duty=value("duty"),
        time=value("time"),
        partner=value("partner"),
        status=value("status"),
        kind=value("type"),
        fields={label: texts[index] for label, index in columns.items()
                if index < len(texts) and texts[index] and texts[index] != "-"},
    )


def _radio_id(row: Element) -> str:
    """The id of the row's selection radio, which the portal uses to act on this swap."""
    radio = row.find(where=lambda e: e.tag == "input"
                     and e.get("type").lower() == "radio" and e.get("id"))
    return radio.get("id") if radio else ""
