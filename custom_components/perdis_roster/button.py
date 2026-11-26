"""A button that asks the portal for the roster right now, instead of waiting for the next poll."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PerdisConfigEntry, coordinator_of
from .entity import PerdisEntity

REFRESH = EntityDescription(key="refresh")


async def async_setup_entry(
    hass: HomeAssistant, entry: PerdisConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([PerdisRefreshButton(coordinator_of(hass, entry), REFRESH)])


class PerdisRefreshButton(PerdisEntity, ButtonEntity):
    """Shown under "Controls" on the device page: no entity category, so it is not tucked away."""

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        # Pressing it is how to retry when the portal was unreachable, so it never greys out.
        return True
