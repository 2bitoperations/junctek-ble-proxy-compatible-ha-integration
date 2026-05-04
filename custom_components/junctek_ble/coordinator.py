from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from bleak import BleakClient
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CHARACTERISTIC_UUID, DOMAIN, PARAMS_KEYS, PARAMS_VALUES

_LOGGER = logging.getLogger(__name__)


class JunctekBLECoordinator(DataUpdateCoordinator[dict]):
    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        battery_capacity: int,
        battery_voltage: int,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self._address = address
        self._battery_capacity = battery_capacity
        self._battery_voltage = battery_voltage
        self._client: BleakClient | None = None
        self._charging = False
        self._cancel_bt_callback: callable | None = None
        self._connect_lock = asyncio.Lock()

    @property
    def address(self) -> str:
        return self._address

    async def async_start(self) -> None:
        self._cancel_bt_callback = bluetooth.async_register_callback(
            self.hass,
            self._handle_bluetooth_event,
            BluetoothCallbackMatcher(address=self._address),
            BluetoothScanningMode.ACTIVE,
        )

    async def async_stop(self) -> None:
        if self._cancel_bt_callback:
            self._cancel_bt_callback()
            self._cancel_bt_callback = None
        client = self._client
        self._client = None
        if client and client.is_connected:
            await client.disconnect()

    @callback
    def _handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        if self._client is None or not self._client.is_connected:
            self.hass.async_create_task(self._async_connect())

    async def _async_connect(self) -> None:
        async with self._connect_lock:
            if self._client and self._client.is_connected:
                return

            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self._address, connectable=True
            )
            if ble_device is None:
                _LOGGER.debug("Device %s not yet connectable", self._address)
                return

            try:
                _LOGGER.debug("Connecting to %s", self._address)
                self._client = await establish_connection(
                    BleakClient,
                    ble_device,
                    self._address,
                    disconnected_callback=self._handle_disconnect,
                )
                await self._client.start_notify(
                    CHARACTERISTIC_UUID, self._notification_handler
                )
                _LOGGER.info("Connected to Junctek %s", self._address)
            except Exception as err:
                _LOGGER.error("Failed to connect to %s: %s", self._address, err)
                self._client = None

    @callback
    def _handle_disconnect(self, client: BleakClient) -> None:
        _LOGGER.debug("Disconnected from %s", self._address)
        self._client = None

    async def _notification_handler(self, _sender: int, value: bytearray) -> None:
        try:
            parsed = self._parse(bytes(value))
            if parsed:
                merged = {**(self.data or {}), **parsed}
                self.async_set_updated_data(merged)
        except Exception as err:
            _LOGGER.error("Error processing notification from %s: %s", self._address, err)

    def _parse(self, raw: bytes) -> dict | None:
        hex_str = raw.hex()
        bs = [hex_str[i:i+2] for i in range(0, len(hex_str), 2)]
        bs_rev = list(reversed(bs))

        raw_values: dict[str, str] = {}
        for i in range(len(bs_rev) - 1):
            if bs_rev[i] in PARAMS_VALUES:
                digits = ""
                j = i + 1
                while j < len(bs_rev) and bs_rev[j].isdigit():
                    digits = bs_rev[j] + digits
                    j += 1
                key = PARAMS_KEYS[PARAMS_VALUES.index(bs_rev[i])]
                raw_values[key] = digits

        if not raw_values:
            return None

        result: dict = {}
        for key, val_str in raw_values.items():
            if not val_str.isdigit():
                continue
            n = int(val_str)

            if key == "voltage":
                v = n / 100
                # Reject obvious garbage (zeros, startup noise). 5 V is below any real
                # battery this monitor would be attached to, so it's a safe floor.
                # The old filter (v > battery_voltage * 0.8) silently dropped valid
                # readings on 12 V batteries when the config defaulted to 48 V.
                if v > 5.0:
                    result[key] = round(v, 2)

            elif key == "current":
                c = n / 100
                if self._charging:
                    c *= -1
                result[key] = round(c, 2)

            elif key == "discharge":
                result[key] = round(n / 100000, 4)
                self._charging = False

            elif key == "charge":
                result[key] = round(n / 100000, 4)
                self._charging = True

            elif key == "dir_of_current":
                self._charging = val_str == "01"

            elif key == "ah_remaining":
                result[key] = round(n / 1000, 3)

            elif key == "mins_remaining":
                result[key] = n

            elif key == "power":
                p = n / 100
                if not self._charging:
                    p *= -1
                result[key] = round(p, 2)

            elif key == "temp":
                t = n - 100
                if t > 10:
                    result[key] = round(t, 1)

            elif key == "accum_charge_cap":
                result[key] = round(n / 1000, 3)

        if "ah_remaining" in result:
            result["soc"] = round(result["ah_remaining"] / self._battery_capacity * 100, 1)

        result["last_message"] = datetime.now().astimezone().isoformat()

        return result
