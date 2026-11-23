"""Makes the dashboard cards available without adding a resource by hand.

The cards ship inside the integration (`frontend/perdis-cards.js`). Home Assistant serves the
folder and loads the script on every dashboard, so the cards show up in the card picker right
after the integration is set up. The version in the address makes browsers fetch a new copy
after an update.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, FRONTEND_SCRIPT, FRONTEND_URL_BASE

_LOGGER = logging.getLogger(__name__)

FRONTEND_FOLDER = Path(__file__).parent / "frontend"
_REGISTERED = f"{DOMAIN}_frontend_registered"


async def async_register_cards(hass: HomeAssistant, version: str) -> None:
    """Serve the card script and load it on every dashboard; does nothing twice."""
    if hass.data.get(_REGISTERED):
        return
    if getattr(hass, "http", None) is None or DATA_EXTRA_MODULE_URL not in hass.data:
        _LOGGER.debug("Frontend not loaded; the Perdis cards are not registered")
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL_BASE, str(FRONTEND_FOLDER), cache_headers=True)]
    )
    add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/{FRONTEND_SCRIPT}?v={version}")
    hass.data[_REGISTERED] = True
