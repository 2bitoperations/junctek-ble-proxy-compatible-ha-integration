from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.const import CONF_ADDRESS
import homeassistant.helpers.config_validation as cv

from .const import CONF_BATTERY_CAPACITY, CONF_BATTERY_VOLTAGE, DOMAIN

_BATTERY_CAPACITY_DEFAULT = 400
_BATTERY_VOLTAGE_DEFAULT  = 48


class JunctekBLEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, str] = {}  # address -> display label

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper().strip()
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Junctek {address}",
                data={
                    CONF_ADDRESS:           address,
                    CONF_BATTERY_CAPACITY:  user_input[CONF_BATTERY_CAPACITY],
                    CONF_BATTERY_VOLTAGE:   user_input[CONF_BATTERY_VOLTAGE],
                },
            )

        already_configured = self._async_current_ids()
        for info in async_discovered_service_info(self.hass):
            if info.address not in already_configured:
                label = f"{info.name} ({info.address})" if info.name else info.address
                self._discovered[info.address] = label

        if self._discovered:
            address_schema = vol.In(self._discovered)
        else:
            address_schema = str

        schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): address_schema,
                vol.Required(CONF_BATTERY_CAPACITY, default=_BATTERY_CAPACITY_DEFAULT): cv.positive_int,
                vol.Required(CONF_BATTERY_VOLTAGE,  default=_BATTERY_VOLTAGE_DEFAULT):  cv.positive_int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
