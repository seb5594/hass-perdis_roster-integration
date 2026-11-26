"""Perdis Duty Roster: the duty roster of a MOBILE-PERDIS portal in Home Assistant.

This is an unofficial integration. INIT does not document the interfaces of WebComm or AppComm;
everything here reads what the portal shows a signed-in employee in the browser.
"""

from __future__ import annotations

import aiohttp

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import create_client
from .const import (
    CONF_BASE_URL,
    CONF_DETAIL_DAYS,
    CONF_PORTAL_TYPE,
    CONF_VERIFY_SSL,
    DEFAULT_DETAIL_DAYS,
    DOMAIN,
    PLATFORMS,
    SECTION_ADVANCED,
    VERSION_KEY,
    PortalType,
    default_time_zone,
)
from .coordinator import PerdisConfigEntry, PerdisCoordinator, discard_coordinator, store_coordinator
from .frontend import async_register_cards
from .services import async_register_services
from .storage import PerdisStore

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register what all accounts share: the services and the dashboard cards."""
    async_register_services(hass)
    integration = await async_get_integration(hass, DOMAIN)
    hass.data[VERSION_KEY] = str(integration.version)
    await async_register_cards(hass, str(integration.version))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PerdisConfigEntry) -> bool:
    """Sign in to the portal of one account and set up its entities."""
    # Each account keeps its own cookies; `unsafe` allows portals that are addressed by IP.
    session = async_create_clientsession(
        hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True), cookie_jar=aiohttp.CookieJar(unsafe=True)
    )
    client = create_client(
        PortalType(entry.data[CONF_PORTAL_TYPE]),
        session,
        entry.data[CONF_BASE_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        default_time_zone(),
        entry.options.get(SECTION_ADVANCED),
        detail_days=entry.options.get(CONF_DETAIL_DAYS, DEFAULT_DETAIL_DAYS),
    )
    coordinator = PerdisCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    store_coordinator(hass, entry, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_changed))
    return True


async def _async_options_changed(hass: HomeAssistant, entry: PerdisConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PerdisConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        discard_coordinator(hass, entry)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: PerdisConfigEntry) -> None:
    """Delete the cached roster together with the account."""
    await PerdisStore(hass, entry.entry_id).async_remove()
