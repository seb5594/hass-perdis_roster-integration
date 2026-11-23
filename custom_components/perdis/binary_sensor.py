"""Binary sensors: yes/no questions about the roster that automations like to ask."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PerdisConfigEntry, PerdisCoordinator
from .entity import PerdisEntity


@dataclass(frozen=True, kw_only=True)
class PerdisBinarySensorDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[PerdisCoordinator], bool | None]
    always_available: bool = False


def _off(coordinator: PerdisCoordinator, offset: int) -> bool | None:
    duty = coordinator.insights.today_duty if offset == 0 else coordinator.insights.tomorrow_duty
    return duty.is_off if duty else None


BINARY_SENSORS: tuple[PerdisBinarySensorDescription, ...] = (
    PerdisBinarySensorDescription(
        key="on_duty", device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda c: c.insights.on_duty,
    ),
    PerdisBinarySensorDescription(key="day_off_today", is_on_fn=lambda c: _off(c, 0)),
    PerdisBinarySensorDescription(key="day_off_tomorrow", is_on_fn=lambda c: _off(c, 1)),
    PerdisBinarySensorDescription(
        key="split_shift_today",
        is_on_fn=lambda c: c.insights.today_duty.split if c.insights.today_duty else None,
    ),
    PerdisBinarySensorDescription(
        key="short_rest", device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda c: c.insights.short_rest,
    ),
    PerdisBinarySensorDescription(
        key="portal_online", device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC, always_available=True,
        is_on_fn=lambda c: bool(c.data and c.data.online and c.last_update_success),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PerdisConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(PerdisBinarySensor(entry.runtime_data, description) for description in BINARY_SENSORS)


class PerdisBinarySensor(PerdisEntity, BinarySensorEntity):
    entity_description: PerdisBinarySensorDescription

    @property
    def available(self) -> bool:
        return self.entity_description.always_available or super().available

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.coordinator)
