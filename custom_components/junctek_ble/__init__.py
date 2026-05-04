from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_BATTERY_CAPACITY, CONF_BATTERY_VOLTAGE, DOMAIN
from .coordinator import JunctekBLECoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = JunctekBLECoordinator(
        hass,
        address=entry.data[CONF_ADDRESS],
        battery_capacity=entry.data[CONF_BATTERY_CAPACITY],
        battery_voltage=entry.data[CONF_BATTERY_VOLTAGE],
    )

    await coordinator.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: JunctekBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_stop()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
