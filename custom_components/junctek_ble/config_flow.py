from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.const import CONF_ADDRESS
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_VOLTAGE,
    CONF_PUSH_INTERVAL,
    CONF_SENSOR_INFIX,
    DEFAULT_PUSH_INTERVAL,
    DOMAIN,
)

_BATTERY_CAPACITY_DEFAULT = 100
_BATTERY_VOLTAGE_DEFAULT  = 12


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
                    CONF_SENSOR_INFIX:      user_input.get(CONF_SENSOR_INFIX, ""),
                    CONF_PUSH_INTERVAL:     user_input.get(CONF_PUSH_INTERVAL, DEFAULT_PUSH_INTERVAL),
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
                vol.Optional(CONF_SENSOR_INFIX,     default=""):                        str,
                vol.Optional(CONF_PUSH_INTERVAL,    default=DEFAULT_PUSH_INTERVAL):      cv.positive_int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return JunctekBLEOptionsFlow(config_entry)


class JunctekBLEOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self._config_entry.data, **self._config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BATTERY_CAPACITY,
                    default=current.get(CONF_BATTERY_CAPACITY, _BATTERY_CAPACITY_DEFAULT),
                ): cv.positive_int,
                vol.Required(
                    CONF_BATTERY_VOLTAGE,
                    default=current.get(CONF_BATTERY_VOLTAGE, _BATTERY_VOLTAGE_DEFAULT),
                ): cv.positive_int,
                vol.Optional(
                    CONF_SENSOR_INFIX,
                    default=current.get(CONF_SENSOR_INFIX, ""),
                ): str,
                vol.Optional(
                    CONF_PUSH_INTERVAL,
                    default=current.get(CONF_PUSH_INTERVAL, DEFAULT_PUSH_INTERVAL),
                ): cv.positive_int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
