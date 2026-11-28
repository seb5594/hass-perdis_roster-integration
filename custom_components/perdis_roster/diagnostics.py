"""Diagnostics download: what a bug report needs, without names and credentials."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import PerdisConfigEntry, coordinator_of

# "partner" is the colleague named in a duty swap; it appears as its own field and inside "details".
TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, "employee_name", "title", "raw", "partner"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: PerdisConfigEntry) -> dict[str, Any]:
    coordinator = coordinator_of(hass, entry)
    data = coordinator.data
    snapshot = data.snapshot if data else None
    return async_redact_data({
        "entry": {"data": dict(entry.data), "options": dict(entry.options), "title": entry.title},
        "portal": {
            "online": data.online if data else None,
            "last_error": data.last_error if data else None,
            "pages": coordinator.client.discovered_pages,
        },
        "snapshot": snapshot.to_dict() if snapshot else None,
        "balance_labels": sorted(snapshot.balances.raw) if snapshot else [],
        "changes": [change.to_dict() for change in data.changes] if data else [],
    }, TO_REDACT)
