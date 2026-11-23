"""Turning the texts a portal shows into dates, times, durations and duty types.

Perdis is used in Germany, Austria, Switzerland and the Netherlands, so every helper accepts the
spellings found there: `23.11.2026` and `2026-11-23`, `12,5` and `12.5`, `+14:30` and `-2:15 h`.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import re
from zoneinfo import ZoneInfo

from ..models import DutyType

DATE_PATTERNS = (
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), ("y", "m", "d")),
    (re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b"), ("d", "m", "y")),
    (re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2})\b(?![.:\d])"), ("d", "m", "yy")),
    (re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(?!\d)"), ("d", "m", None)),
)
CLOCK = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?![\d:])")
TIME_RANGE = re.compile(r"(?<![\d:])(\d{1,2}:\d{2})\s*(?:-|–|—|bis|to|tot)\s*(\d{1,2}:\d{2})(?![\d:])")
SIGNED_CLOCK = re.compile(r"^([+-])?\s*(\d{1,4}):(\d{2})")
NUMBER = re.compile(r"[+-]?\d[\d.,']*")
LINE_NUMBER = re.compile(r"\b[A-Z]{0,3}\d{1,4}[A-Z]?\b")


def parse_date(text: str, today: date) -> date | None:
    """The first date in `text`; a date without a year is put in the year closest to today."""
    for pattern, order in DATE_PATTERNS:
        found = pattern.search(text)
        if not found:
            continue
        parts = dict(zip(order, found.groups(), strict=False))
        day, month = int(parts["d"]), int(parts["m"])
        if "y" in parts:
            years = [int(parts["y"])]
        elif "yy" in parts:
            years = [2000 + int(parts["yy"])]
        else:
            years = [today.year - 1, today.year, today.year + 1]
        candidates = []
        for year in years:
            try:
                candidates.append(date(year, month, day))
            except ValueError:
                continue
        if candidates:
            return min(candidates, key=lambda candidate: abs((candidate - today).days))
    return None


def clock_minutes(text: str) -> int | None:
    """Minutes since the start of the operating day; `25:45` is 1545, past midnight."""
    found = CLOCK.search(text)
    if not found:
        return None
    hours, minutes = int(found.group(1)), int(found.group(2))
    return hours * 60 + minutes if minutes < 60 and hours < 48 else None


def time_ranges(text: str) -> list[tuple[int, int]]:
    """Every `start - end` pair in `text` as operating-day minutes."""
    ranges = []
    for start, end in TIME_RANGE.findall(text):
        start_minutes, end_minutes = clock_minutes(start), clock_minutes(end)
        if start_minutes is not None and end_minutes is not None:
            ranges.append((start_minutes, end_minutes))
    return ranges


def operating_time(day: date, minutes: int, zone: ZoneInfo) -> datetime:
    """The real point in time of `minutes` after the start of the operating `day`."""
    extra_days, minute_of_day = divmod(minutes, 24 * 60)
    clock = time(minute_of_day // 60, minute_of_day % 60)
    return datetime.combine(day + timedelta(days=extra_days), clock, tzinfo=zone)


def shift_times(day: date, start: int, end: int, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """Start and end of a shift; an end before the start means the shift runs past midnight."""
    if end <= start:
        end += 24 * 60
    return operating_time(day, start, zone), operating_time(day, end, zone)


def parse_number(text: str) -> float | None:
    """`1.234,5`, `1,234.5`, `12,5` and `12.5` all become numbers."""
    found = NUMBER.search(text.replace("−", "-"))
    if not found:
        return None
    raw = found.group(0).replace("'", "").rstrip(".,")
    if "," in raw and "." in raw:
        decimal = "," if raw.rfind(",") > raw.rfind(".") else "."
        raw = raw.replace("." if decimal == "," else ",", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_duration(text: str) -> int | None:
    """Signed minutes from `+14:30`, `-2:15 h`, `12,5 Std.` or `750 min`."""
    cleaned = text.strip().replace("−", "-")
    clock = SIGNED_CLOCK.search(cleaned)
    if clock:
        minutes = int(clock.group(2)) * 60 + int(clock.group(3))
        return -minutes if clock.group(1) == "-" else minutes
    value = parse_number(cleaned)
    if value is None:
        return None
    return round(value) if re.search(r"\bmin", cleaned, re.IGNORECASE) else round(value * 60)


def line_numbers(text: str) -> list[str]:
    """Line numbers such as `U79`, `705` or `SB19` mentioned in a text."""
    return list(dict.fromkeys(LINE_NUMBER.findall(text)))


# --- Duty types ------------------------------------------------------------------------------
# Absence codes differ per operator; these are the ones seen in German, Austrian and Dutch
# portals. A code that is not listed is a duty number when it contains digits or comes with times.
DUTY_CODES: dict[str, DutyType] = {
    **dict.fromkeys(
        ("R", "F", "FR", "FREI", "RT", "RUHE", "RUHETAG", "X", "AT", "VRIJ", "RD", "AB", "STR"),
        DutyType.FREE,
    ),
    **dict.fromkeys(
        ("U", "UR", "URL", "URLAUB", "EU", "ZU", "SU", "BU", "V", "VERLOF", "VAC"),
        DutyType.VACATION,
    ),
    **dict.fromkeys(
        ("K", "KR", "KRANK", "AU", "KU", "ZIEK", "SICK", "KOS"),
        DutyType.SICK,
    ),
    **dict.fromkeys(
        ("FA", "ZA", "AZV", "FZA", "GLZ", "UA", "ADV", "ÜA", "UEA", "FM", "ET"),
        DutyType.COMPENSATION,
    ),
    **dict.fromkeys(
        ("S", "SCH", "SCHUL", "SCHULUNG", "DA", "BA", "UW", "FS", "OPL", "TRAINING"),
        DutyType.TRAINING,
    ),
    **dict.fromkeys(
        ("B", "BE", "BER", "BEREIT", "RES", "RESERVE", "RS", "BD"),
        DutyType.RESERVE,
    ),
}
REMARK_WORDS: tuple[tuple[tuple[str, ...], DutyType], ...] = (
    (("urlaub", "verlof", "vacation", "holiday"), DutyType.VACATION),
    (("krank", "ziek", "sick"), DutyType.SICK),
    (("freizeitausgleich", "zeitausgleich", "überstundenabbau", "compensat"), DutyType.COMPENSATION),
    (("schulung", "seminar", "fortbildung", "unterweisung", "opleiding", "training"), DutyType.TRAINING),
    (("bereitschaft", "reserve", "springer"), DutyType.RESERVE),
    (("frei", "ruhetag", "vrij", "day off"), DutyType.FREE),
)


def classify_duty(code: str, remark: str = "", has_times: bool = False) -> DutyType:
    """The duty type behind an entry, from its code, its remark and whether it has times."""
    normalized = code.strip().upper().rstrip(".")
    if normalized in DUTY_CODES:
        return DUTY_CODES[normalized]
    if re.fullmatch(r"(RES|BER|BD)\s*\d+", normalized):
        return DutyType.RESERVE
    words = f"{code} {remark}".lower()
    for keywords, duty_type in REMARK_WORDS:
        if any(keyword in words for keyword in keywords) and not (duty_type is DutyType.FREE and has_times):
            return duty_type
    if has_times or any(character.isdigit() for character in normalized):
        return DutyType.WORK
    return DutyType.UNKNOWN


WEEKDAY_NAMES = frozenset({
    "mo", "di", "mi", "do", "fr", "sa", "so", "montag", "dienstag", "mittwoch", "donnerstag", "freitag",
    "samstag", "sonnabend", "sonntag", "ma", "wo", "vr", "za", "zo", "maandag", "dinsdag", "woensdag",
    "donderdag", "vrijdag", "zaterdag", "zondag", "mon", "tue", "wed", "thu", "fri", "sat", "sun",
})


def is_weekday_name(text: str) -> bool:
    """True for `Mo`, `Montag`, `Mon.` and their Dutch and English counterparts."""
    return text.strip().rstrip(".,").lower() in WEEKDAY_NAMES


def normalize_label(text: str) -> str:
    """A column or row label reduced to lower case words, for keyword matching."""
    return re.sub(r"[^\wäöüß%/+-]+", " ", text.lower()).strip()
