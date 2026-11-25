"""Human names for the duty types, shared by the calendar and the change notifications."""

from __future__ import annotations

from .models import DutyType

# One readable name per duty type and language. The calendar titles and the change messages both
# read from here, so a day off always reads the same wherever it is shown.
DUTY_TYPE_LABELS: dict[str, dict[DutyType, str]] = {
    "en": {
        DutyType.FREE: "Day off", DutyType.VACATION: "Vacation", DutyType.SICK: "Sick leave",
        DutyType.COMPENSATION: "Time off in lieu", DutyType.TRAINING: "Training",
        DutyType.RESERVE: "Reserve", DutyType.WORK: "Duty", DutyType.UNKNOWN: "Roster",
    },
    "de": {
        DutyType.FREE: "Frei", DutyType.VACATION: "Urlaub", DutyType.SICK: "Krank",
        DutyType.COMPENSATION: "Freizeitausgleich", DutyType.TRAINING: "Schulung",
        DutyType.RESERVE: "Bereitschaft", DutyType.WORK: "Dienst", DutyType.UNKNOWN: "Dienstplan",
    },
}


def duty_type_labels(language: str) -> dict[DutyType, str]:
    """The duty-type names for a Home Assistant language code such as "de" or "en-GB"."""
    return DUTY_TYPE_LABELS.get(language.split("-", 1)[0].lower(), DUTY_TYPE_LABELS["en"])


def type_label(duty_type: DutyType, language: str) -> str:
    """The readable name of one duty type, e.g. "Krank" / "Sick leave"."""
    return duty_type_labels(language)[duty_type]
