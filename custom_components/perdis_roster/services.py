"""Services: refresh the roster on demand and hand duties to scripts and automations."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

try:  # Service responses (a service that returns data) arrived in Home Assistant 2023.7.
    from homeassistant.core import ServiceResponse, SupportsResponse
except ImportError:  # pragma: no cover - older cores cannot return a response
    ServiceResponse = dict
    SupportsResponse = None

try:  # ServiceValidationError arrived in 2024.1, its translated form in 2024.2.
    from homeassistant.exceptions import ServiceValidationError
except ImportError:  # pragma: no cover - older cores only have the generic error
    from homeassistant.exceptions import HomeAssistantError as ServiceValidationError

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_END_DATE,
    ATTR_START_DATE,
    DOMAIN,
    SERVICE_GET_DUTIES,
    SERVICE_REFRESH,
)
from .coordinator import coordinator_of
from .insights import shift_category

if TYPE_CHECKING:
    from .coordinator import PerdisCoordinator

DEFAULT_RANGE = timedelta(days=13)  # two weeks including today

# English fall-backs for the cores that cannot show a translated validation error.
_ERROR_MESSAGES = {
    "no_loaded_entry": "No Perdis account is set up and loaded.",
    "end_before_start": "The end date is before the start date.",
}


def _validation_error(key: str) -> Exception:
    """A translated ServiceValidationError, or a plain message on cores that lack the translated form."""
    try:
        return ServiceValidationError(translation_domain=DOMAIN, translation_key=key)
    except TypeError:  # pragma: no cover - older cores take a plain message only
        return ServiceValidationError(_ERROR_MESSAGES[key])


REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})
GET_DUTIES_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Optional(ATTR_START_DATE): cv.date,
    vol.Optional(ATTR_END_DATE): cv.date,
})


def _coordinators(hass: HomeAssistant, entry_id: str | None) -> list[PerdisCoordinator]:
    """The loaded accounts, or the one chosen in the call."""
    entries = [entry for entry in hass.config_entries.async_entries(DOMAIN)
               if entry.state is ConfigEntryState.LOADED and (entry_id is None or entry.entry_id == entry_id)]
    if not entries:
        raise _validation_error("no_loaded_entry")
    return [coordinator_of(hass, entry) for entry in entries]


@callback
def async_register_services(hass: HomeAssistant) -> None:
    async def refresh(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call.data.get(ATTR_CONFIG_ENTRY_ID)):
            await coordinator.async_request_refresh()

    async def get_duties(call: ServiceCall) -> ServiceResponse:
        coordinators = _coordinators(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        first: date = call.data.get(ATTR_START_DATE) or coordinators[0].insights.today
        last: date = call.data.get(ATTR_END_DATE) or first + DEFAULT_RANGE
        if last < first:
            raise _validation_error("end_before_start")
        return {"accounts": [_account_response(coordinator, first, last) for coordinator in coordinators]}

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, refresh, schema=REFRESH_SCHEMA)
    if SupportsResponse is not None:
        hass.services.async_register(DOMAIN, SERVICE_GET_DUTIES, get_duties, schema=GET_DUTIES_SCHEMA,
                                     supports_response=SupportsResponse.ONLY)
    else:  # pragma: no cover - cores before 2023.7 cannot hand the duties back as a response
        hass.services.async_register(DOMAIN, SERVICE_GET_DUTIES, get_duties, schema=GET_DUTIES_SCHEMA)


def _account_response(coordinator: PerdisCoordinator, first: date, last: date) -> dict[str, Any]:
    insights = coordinator.insights
    duties = [duty for duty in insights.duties if first <= duty.day <= last]
    return {
        "config_entry_id": coordinator.config_entry.entry_id,
        "title": coordinator.config_entry.title,
        "duties": [{**duty.to_dict(), "category": (c.value if (c := shift_category(duty)) else None)}
                   for duty in duties],
        "planned_hours": round(insights.planned_minutes(first, last) / 60, 2),
    }
