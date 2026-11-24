"""Reading rosters and account overviews out of HTML tables, whatever the operator calls the columns.

WebComm is configured per operator: one portal labels a column "Beginn", the next "Dienstbeginn"
or "Aanvang". Instead of fixed positions, columns are recognised by their header text. A table
without a header row is read with a fallback that looks at what the cells contain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import re

from .html import Element, innermost_tables, table_rows
from .values import normalize_label, parse_date

# Column keys and the header texts that mean them, most specific first.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("datum", "date", "dag", "datum/tag", "tag"),
    "weekday": ("wochentag", "wt", "weekday", "weekdag"),
    "start": ("dienstbeginn", "beginn", "begin", "anfang", "start", "von", "aanvang", "from"),
    "end": ("dienstende", "ende", "end", "einde", "eind", "bis", "to", "tot"),
    "start_location": ("beginnort", "antrittsort", "dienstantritt", "meldeort", "ort von", "start location",
                       "beginplaats", "beginlocatie", "ort", "plaats", "location"),
    "end_location": ("endort", "ablöseort", "abloeseort", "ort bis", "end location", "eindplaats", "eindlocatie"),
    "duty": ("dienstnummer", "dienstnr", "dienst nr", "dienst", "schicht", "dienstart", "kürzel", "kuerzel",
             "code", "duty", "shift", "dienstcode"),
    "paid": ("bezahlte zeit", "bez zeit", "bezahlt", "arbeitszeit", "az", "dauer", "duration", "paid", "werktijd",
             "diensttijd", "dienstdauer"),
    "break": ("pausen", "pause", "break", "pauze"),
    "lines": ("linien", "linie", "lines", "line", "lijn", "lijnen"),
    "remark": ("bemerkung", "bemerkungen", "hinweis", "info", "text", "beschreibung", "bezeichnung", "comment",
               "remark", "opmerking", "omschrijving"),
}


# "Resturlaub: 12,5 Tage", "Saldo: +14:30 h": a label, a colon and a number with an optional unit.
LABEL_AND_VALUE = re.compile(
    r"([^:\d][^:]{2,60}):\s*([+\-\u2212]?\d[\d.,:]*\s*(?:h|std\.?|stunden|tage?|d|min|pkt\.?|punkte)?)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class DayRow:
    """One table row that belongs to a day; several rows can belong to the same day."""

    day: date
    cells: dict[str, str] = field(default_factory=dict)
    loose: list[str] = field(default_factory=list)  # cells of a table without a known header


def match_columns(header: list[str]) -> dict[int, str]:
    """Column index -> column key, for the header cells that could be recognised."""
    labels = [normalize_label(text) for text in header]
    mapping: dict[int, str] = {}
    taken: set[str] = set()
    # Pass 1: exact header texts. Pass 2: the longest alias contained in a header text.
    for index, label in enumerate(labels):
        for key, aliases in COLUMN_ALIASES.items():
            if key not in taken and label in aliases:
                mapping[index] = key
                taken.add(key)
                break
    candidates = sorted(
        ((alias, key) for key, aliases in COLUMN_ALIASES.items() for alias in aliases if len(alias) > 3),
        key=lambda pair: -len(pair[0]),
    )
    for index, label in enumerate(labels):
        if index in mapping or not label:
            continue
        for alias, key in candidates:
            if key not in taken and re.search(rf"(^|\b){re.escape(alias)}", label):
                mapping[index] = key
                taken.add(key)
                break
    return mapping


def roster_rows(document: Element, today: date) -> list[DayRow]:
    """Every row of every table on the page that names a day, the best-labelled tables first."""
    rows: list[DayRow] = []
    for table in innermost_tables(document):
        mapping: dict[int, str] = {}
        for is_header, cells in table_rows(table):
            if is_header or (not mapping and _looks_like_header(cells, today)):
                found = match_columns(cells)
                if "date" in found.values() or len(found) >= 3:
                    mapping = found
                continue
            row = _day_row(cells, mapping, today)
            if row:
                rows.append(row)
    return rows


def _looks_like_header(cells: list[str], today: date) -> bool:
    """A row of labels in a table that marks its header with `td` instead of `th`."""
    return len(match_columns(cells)) >= 3 and not any(parse_date(cell, today) for cell in cells)


def _day_row(cells: list[str], mapping: dict[int, str], today: date) -> DayRow | None:
    date_columns = [index for index, key in mapping.items() if key == "date"]
    searched = [cells[index] for index in date_columns if index < len(cells)] or cells[:3]
    day = next((found for cell in searched if (found := parse_date(cell, today))), None)
    if day is None:
        return None
    row = DayRow(day)
    for index, text in enumerate(cells):
        key = mapping.get(index)
        if key in {"date", "weekday"} or (key is None and index in date_columns):
            continue
        if key:
            row.cells[key] = f"{row.cells[key]} {text}".strip() if key in row.cells else text
        elif text and not parse_date(text, today):
            row.loose.append(text)
    return row


def _has_digit(text: str) -> bool:
    return any(char.isdigit() for char in text)


def _row_pairs(filled: list[str]) -> list[tuple[str, str]]:
    """The label/value pairs carried by one table row, in whichever shape the portal uses.

    * ``Label | value`` — a plain two-column row.
    * ``Label | value | Label | value | ...`` — a "key-value table" that packs several accounts
      into one row (every even cell is a label, every odd cell its value).
    * ``Account | from | to | value | ...`` — a record row whose value is the last column; the
      first cell labels it and the columns in between (dates, ids) are ignored.
    """
    if len(filled) < 2 or _has_digit(filled[0]):
        return []
    labels, values = filled[0::2], filled[1::2]
    if len(filled) >= 4 and len(filled) % 2 == 0 \
            and not any(_has_digit(label) for label in labels) and all(_has_digit(value) for value in values):
        return list(zip(labels, values, strict=True))
    return [(filled[0], filled[-1])]


def key_values(document: Element) -> dict[str, str]:
    """Label -> value pairs of a page: label/value table rows and `Label: value` texts."""
    pairs: dict[str, str] = {}
    for table in innermost_tables(document):
        for _, cells in table_rows(table):
            for label, value in _row_pairs([cell for cell in cells if cell]):
                pairs.setdefault(label.rstrip(":").strip(), value.strip())
    for element in document.find_all({"span", "div", "p", "li", "label", "dd", "td"}):
        text = element.text()
        found = LABEL_AND_VALUE.fullmatch(text)
        if found:
            pairs.setdefault(found.group(1).strip(), found.group(2).strip())
    return pairs


def lookup(pairs: dict[str, str], keywords: tuple[str, ...], exclude: tuple[str, ...] = ()) -> str | None:
    """The value of the first label that contains one of the keywords (whole words for short ones)."""
    for keyword in keywords:
        pattern = re.compile(rf"\b{re.escape(keyword)}\b" if len(keyword) <= 4 else re.escape(keyword))
        for label, value in pairs.items():
            normalized = normalize_label(label)
            if pattern.search(normalized) and not any(word in normalized for word in exclude):
                return value
    return None
