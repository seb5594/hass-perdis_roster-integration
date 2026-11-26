"""The base of every PERDIS entity: one device per account, names from the translations."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType

try:  # DeviceInfo moved from helpers.entity to helpers.device_registry in Home Assistant 2024.1.
    from homeassistant.helpers.device_registry import DeviceInfo
except ImportError:  # pragma: no cover - older cores keep it in helpers.entity
    from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_BASE_URL, CONF_PORTAL_TYPE, DOMAIN, MANUFACTURER, VERSION_KEY
from .coordinator import PerdisCoordinator
from .operators import find_operator_by_url

# Attribute the dashboard cards use to find the entities of an account, whatever they are named.
ATTR_ROLE = "perdis_role"


def description_frozen(base: type) -> bool:
    """Whether a Home Assistant entity-description base is a frozen dataclass.

    Entity descriptions became frozen dataclasses in Home Assistant 2024.1. A subclass must match
    its base (a frozen dataclass cannot inherit from a non-frozen one, and vice versa), so the
    platform descriptions read their `frozen` from here instead of hard-coding it.
    """
    params = getattr(base, "__dataclass_params__", None)
    return bool(params and params.frozen)


class PerdisEntity(CoordinatorEntity[PerdisCoordinator]):
    """Shares the device and the unique id scheme."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PerdisCoordinator, description: EntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_translation_key = description.translation_key or description.key
        operator = find_operator_by_url(entry.data[CONF_BASE_URL])
        portal = "AppComm" if entry.data[CONF_PORTAL_TYPE] == "appcomm" else "WebComm"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=f"PERDIS {portal}" + (f" · {operator.name}" if operator else ""),
            configuration_url=entry.data[CONF_BASE_URL],
            # The version that is running, not the one on disk: after an update it shows the old
            # one until Home Assistant restarts, which is exactly what is worth seeing.
            sw_version=coordinator.hass.data.get(VERSION_KEY),
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Cached data counts as available: the roster is still valid while the portal is down."""
        return self.coordinator.data is not None and self.coordinator.data.snapshot is not None
