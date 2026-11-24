"""Services: refresh the roster on demand and hand duties to scripts and automations."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_END_DATE,
    ATTR_PARTNER,
    ATTR_START_DATE,
    ATTR_SWAP_ID,
    ATTR_VALIDATE_ONLY,
    DOMAIN,
    SERVICE_GET_DUTIES,
    SERVICE_REFRESH,
    SERVICE_SWAP_ACCEPT,
    SERVICE_SWAP_REJECT,
    SERVICE_SWAP_REQUEST,
    SERVICE_SWAP_WITHDRAW,
)
from .insights import shift_category

if TYPE_CHECKING:
    from .coordinator import PerdisCoordinator

DEFAULT_RANGE = timedelta(days=13)  # two weeks including today

REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})
GET_DUTIES_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Optional(ATTR_START_DATE): cv.date,
    vol.Optional(ATTR_END_DATE): cv.date,
})
SWAP_REQUEST_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Required(ATTR_START_DATE): cv.date,
    vol.Optional(ATTR_END_DATE): cv.date,
    vol.Optional(ATTR_PARTNER): cv.string,
    vol.Optional(ATTR_VALIDATE_ONLY, default=False): cv.boolean,
})
SWAP_ACTION_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Required(ATTR_SWAP_ID): cv.string,
})


def _coordinators(hass: HomeAssistant, entry_id: str | None) -> list[PerdisCoordinator]:
    """The loaded accounts, or the one chosen in the call."""
    entries = [entry for entry in hass.config_entries.async_entries(DOMAIN)
               if entry.state is ConfigEntryState.LOADED and (entry_id is None or entry.entry_id == entry_id)]
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_loaded_entry")
    return [entry.runtime_data for entry in entries]


def _swap_coordinator(hass: HomeAssistant, entry_id: str | None) -> PerdisCoordinator:
    """The one account a swap action applies to; needs a choice when several are set up."""
    coordinators = _coordinators(hass, entry_id)
    if entry_id is None and len(coordinators) > 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="choose_account")
    coordinator = coordinators[0]
    if not coordinator.client.supports_swaps:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="swaps_unsupported")
    return coordinator


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
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="end_before_start")
        return {"accounts": [_account_response(coordinator, first, last) for coordinator in coordinators]}

    async def swap_request(call: ServiceCall) -> ServiceResponse:
        coordinator = _swap_coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        start: date = call.data[ATTR_START_DATE]
        end: date = call.data.get(ATTR_END_DATE) or start
        if end < start:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="end_before_start")
        message = await coordinator.async_request_swap(
            start, end, call.data.get(ATTR_PARTNER, ""), check=call.data[ATTR_VALIDATE_ONLY])
        return {"message": message}

    def swap_resolver(action: str):
        async def resolve(call: ServiceCall) -> ServiceResponse:
            coordinator = _swap_coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
            message = await coordinator.async_resolve_swap(action, call.data[ATTR_SWAP_ID])
            return {"message": message}

        return resolve

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, refresh, schema=REFRESH_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_GET_DUTIES, get_duties, schema=GET_DUTIES_SCHEMA,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, SERVICE_SWAP_REQUEST, swap_request, schema=SWAP_REQUEST_SCHEMA,
                                 supports_response=SupportsResponse.OPTIONAL)
    for service, action in ((SERVICE_SWAP_ACCEPT, "accept"), (SERVICE_SWAP_REJECT, "reject"),
                            (SERVICE_SWAP_WITHDRAW, "withdraw")):
        hass.services.async_register(DOMAIN, service, swap_resolver(action), schema=SWAP_ACTION_SCHEMA,
                                     supports_response=SupportsResponse.OPTIONAL)


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
