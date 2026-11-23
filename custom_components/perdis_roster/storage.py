"""The last snapshot and the change history, kept in Home Assistant's `.storage` folder.

The roster stays available while the portal is down for maintenance, and a restart of Home
Assistant does not report the whole roster as "changed". The file is only written when its
content actually changed, which spares the SD card of a Raspberry Pi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .models import ScheduleChange, Snapshot

STORAGE_VERSION = 1


@dataclass(slots=True)
class StoredState:
    snapshot: Snapshot | None = None
    changes: list[ScheduleChange] = field(default_factory=list)
    capabilities: frozenset[str] = frozenset()

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "changes": [change.to_dict() for change in self.changes],
            "capabilities": sorted(self.capabilities),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredState:
        snapshot = data.get("snapshot")
        return cls(
            snapshot=Snapshot.from_dict(snapshot) if snapshot else None,
            changes=[ScheduleChange.from_dict(item) for item in data.get("changes", [])],
            capabilities=frozenset(data.get("capabilities", [])),
        )


class PerdisStore:
    """Reads and writes the `StoredState` of one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")
        self._written: dict[str, Any] | None = None

    async def async_load(self) -> StoredState:
        data = await self._store.async_load()
        if not data:
            return StoredState()
        self._written = data
        try:
            return StoredState.from_dict(data)
        except (KeyError, TypeError, ValueError):  # a damaged file only costs the cache
            return StoredState()

    async def async_save(self, state: StoredState) -> None:
        """Write the state unless only the time of the refresh differs from the file."""
        data = state.to_dict()
        if _without_refresh_time(data) != _without_refresh_time(self._written):
            await self._store.async_save(data)
            self._written = data

    async def async_remove(self) -> None:
        await self._store.async_remove()


def _without_refresh_time(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data or not data.get("snapshot"):
        return data
    return {**data, "snapshot": {**data["snapshot"], "fetched_at": None}}
