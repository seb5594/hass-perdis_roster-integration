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
from homeassistant.core import HomeAssistant

try:  # StaticPathConfig and async_register_static_paths arrived in Home Assistant 2024.7.
    from homeassistant.components.http import StaticPathConfig
except ImportError:  # older cores register the static folder synchronously instead
    StaticPathConfig = None

from .const import DOMAIN, FRONTEND_SCRIPT, FRONTEND_URL_BASE

_LOGGER = logging.getLogger(__name__)

FRONTEND_FOLDER = Path(__file__).parent / "frontend"
_REGISTERED = f"{DOMAIN}_frontend_registered"


async def async_register_cards(hass: HomeAssistant, version: str) -> None:
    """Serve the card script and load it on every dashboard; does nothing twice."""
    if hass.data.get(_REGISTERED):
        return
    if getattr(hass, "http", None) is None or DATA_EXTRA_MODULE_URL not in hass.data:
        # "frontend" is a manifest dependency, so this should not happen; warn if it ever does, so
        # a missing card picker is traceable instead of failing silently.
        _LOGGER.warning("Home Assistant frontend not ready; the Perdis dashboard cards were not registered")
        return
    folder = str(FRONTEND_FOLDER)
    if StaticPathConfig is not None and hasattr(hass.http, "async_register_static_paths"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL_BASE, folder, cache_headers=True)]
        )
    else:  # Home Assistant before 2024.7
        hass.http.register_static_path(FRONTEND_URL_BASE, folder, cache_headers=True)
    add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/{FRONTEND_SCRIPT}?v={version}")
    hass.data[_REGISTERED] = True
    # Logged at info so the user can confirm in the log that the cards are served; the card picker
    # then lists them after a browser refresh (they are loaded as a frontend module, so they do not
    # show up under Settings > Dashboards > Resources).
    _LOGGER.info("Perdis dashboard cards served from %s/%s", FRONTEND_URL_BASE, FRONTEND_SCRIPT)
