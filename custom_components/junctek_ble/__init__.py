from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_VOLTAGE,
    CONF_PUSH_INTERVAL,
    DEFAULT_PUSH_INTERVAL,
    DOMAIN,
)
from .coordinator import JunctekBLECoordinator

PLATFORMS = [Platform.SENSOR]


def _entry_value(entry: ConfigEntry, key: str, default: int | None = None) -> int:
    """Read a value from options first, falling back to data (set at config time)."""
    if default is None:
        return entry.options.get(key, entry.data[key])
    return entry.options.get(key, entry.data.get(key, default))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = JunctekBLECoordinator(
        hass,
        address=entry.data[CONF_ADDRESS],
        battery_capacity=_entry_value(entry, CONF_BATTERY_CAPACITY),
        battery_voltage=_entry_value(entry, CONF_BATTERY_VOLTAGE),
        push_interval=_entry_value(entry, CONF_PUSH_INTERVAL, DEFAULT_PUSH_INTERVAL),
    )

    await coordinator.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: JunctekBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_stop()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
