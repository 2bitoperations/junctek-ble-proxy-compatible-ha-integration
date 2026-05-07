from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

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

from .const import CHARACTERISTIC_UUID, DOMAIN, PARAMS_KEYS, PARAMS_VALUES, WRITE_CHARACTERISTIC_UUID

_LOGGER = logging.getLogger(__name__)

_WATCHDOG_INTERVAL = 60      # seconds between watchdog checks
_STALE_THRESHOLD   = 120     # seconds without data before forcing reconnect
_PACKET_LOG_MAX    = 200     # rolling buffer size for CRC/frame diagnostics


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
        self._last_data_time: datetime | None = None
        self._watchdog_task: asyncio.Task | None = None
        self._packet_log: list[str] = []

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
        self._watchdog_task = self.hass.async_create_background_task(
            self._watchdog_loop(), "junctek_ble_watchdog"
        )

    async def async_stop(self) -> None:
        if self._watchdog_task:
            self._watchdog_task.cancel()
            self._watchdog_task = None
        if self._cancel_bt_callback:
            self._cancel_bt_callback()
            self._cancel_bt_callback = None
        client = self._client
        self._client = None
        if client and client.is_connected:
            await client.disconnect()

    async def _watchdog_loop(self) -> None:
        while True:
            await asyncio.sleep(_WATCHDOG_INTERVAL)
            await self._check_stale()

    async def _check_stale(self) -> None:
        if self._last_data_time is None:
            return
        age = datetime.now() - self._last_data_time
        if age < timedelta(seconds=_STALE_THRESHOLD):
            return
        _LOGGER.warning(
            "No data from %s in %.0f s — forcing reconnect",
            self._address,
            age.total_seconds(),
        )
        client = self._client
        self._client = None
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass

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
                _LOGGER.info("Connecting to %s", self._address)
                self._client = await establish_connection(
                    BleakClient,
                    ble_device,
                    self._address,
                    disconnected_callback=self._handle_disconnect,
                )
                await self._client.start_notify(
                    CHARACTERISTIC_UUID, self._notification_handler
                )
                await self._write_device_config()
                # Poll after 1 s — mirrors the app's post-subscribe writeData("9ae0")
                # which causes the device to send a full data dump (including c0/voltage).
                # Without this, voltage and other fields are never transmitted.
                self.hass.async_create_background_task(
                    self._async_initial_poll(), "junctek_ble_initial_poll"
                )
                _LOGGER.info("Connected to Junctek %s", self._address)
            except Exception as err:
                _LOGGER.error("Failed to connect to %s: %s", self._address, err)
                self._client = None

    @callback
    def _handle_disconnect(self, client: BleakClient) -> None:
        _LOGGER.info("Disconnected from %s", self._address)
        self._client = None

    async def _async_initial_poll(self) -> None:
        """Send the 9ae0 poll 1 s after subscribing to trigger a full data flush from the device."""
        await asyncio.sleep(1)
        if self._client is None or not self._client.is_connected:
            return
        payload = self._frame_command("9ae0")
        await self._write_to_device(payload, label="initial poll (9ae0)")

    async def _write_device_config(self) -> None:
        """Write battery capacity preset (b0) to the device after connecting."""
        if not self._battery_capacity or self._client is None:
            return
        payload = self._build_capacity_write(self._battery_capacity)
        await self._write_to_device(payload, label=f"capacity preset ({self._battery_capacity} Ah)")

    async def _write_to_device(self, payload: bytes, label: str) -> None:
        """Write bytes to the write characteristic, logging the attempt and result."""
        hex_str = payload.hex()
        self._packet_log.append(f"WRITE:{hex_str}")
        while len(self._packet_log) > _PACKET_LOG_MAX:
            self._packet_log.pop(0)
        _LOGGER.info("Sending %s to %s: %s", label, self._address, hex_str)
        try:
            await self._client.write_gatt_char(WRITE_CHARACTERISTIC_UUID, payload)
            _LOGGER.info("Sent %s to %s OK", label, self._address)
        except Exception as err:
            _LOGGER.warning("Failed to send %s to %s: %s", label, self._address, err)

    @staticmethod
    def _frame_command(cmd_hex: str) -> bytes:
        """Wrap a hex command string in BB..EE framing with BCD checksum."""
        frame = bytes.fromhex("bb" + cmd_hex)
        n = sum(frame) % 100
        checksum = ((n // 10) << 4) | (n % 10)
        return frame + bytes([checksum, 0xEE])

    @staticmethod
    def _build_capacity_write(capacity_ah: float) -> bytes:
        """Build a b0 capacity-preset write frame for the given capacity in Ah."""
        raw = min(int(capacity_ah * 10), 99999)
        value_str = str(raw)
        if len(value_str) % 2:
            value_str = "0" + value_str
        return JunctekBLECoordinator._frame_command("9ab0" + value_str + "b0")

    async def _notification_handler(self, _sender: int, value: bytearray) -> None:
        try:
            parsed = self._parse(bytes(value))
            if parsed:
                self._last_data_time = datetime.now()
                merged = {**(self.data or {}), **parsed}
                self.async_set_updated_data(merged)
        except Exception as err:
            _LOGGER.error("Error processing notification from %s: %s", self._address, err)

    @staticmethod
    def _split_frames(raw: bytes) -> list[bytes]:
        """Split a BLE notification payload into bb..ee frames."""
        frames = []
        i = 0
        while i < len(raw):
            if raw[i] == 0xBB:
                try:
                    end = raw.index(0xEE, i + 1)
                    frames.append(raw[i:end + 1])
                    i = end + 1
                except ValueError:
                    break
            else:
                i += 1
        return frames

    @staticmethod
    def _checksum_valid(frame: bytes) -> bool:
        """Validate frame CRC: BCD(sum(bb..pre_checksum) % 100) == checksum_byte."""
        if len(frame) < 4:
            return False
        n = sum(frame[:-2]) % 100
        expected = ((n // 10) << 4) | (n % 10)
        return frame[-2] == expected

    def _parse(self, raw: bytes) -> dict | None:
        frames = self._split_frames(raw)
        valid_frames: list[bytes] = []

        if frames:
            for frame in frames:
                valid = self._checksum_valid(frame)
                self._packet_log.append(f"{'OK' if valid else 'BAD'}:{frame.hex()}")
                if valid:
                    valid_frames.append(frame)
        else:
            # No bb..ee framing found — log raw and try to parse anyway.
            self._packet_log.append(f"RAW:{raw.hex()}")
            valid_frames = [raw]

        while len(self._packet_log) > _PACKET_LOG_MAX:
            self._packet_log.pop(0)

        result: dict = {}
        for frame in valid_frames:
            parsed = self._parse_frame(frame)
            if parsed:
                result.update(parsed)

        if not result:
            return None

        result["last_message"] = datetime.now().astimezone().isoformat()
        result["_raw_hex"] = raw.hex()
        return result

    def _parse_frame(self, raw: bytes) -> dict | None:
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
                if self._charging:
                    p *= -1
                result[key] = round(p, 2)

            elif key == "int_resistance":
                # d7 encodes battery internal resistance in mΩ (n / 100 = mΩ).
                # Confirmed from Junctek app APK: labelled "IntRes" on KG-F page.
                # The KL/BTG656 page does not display d7, but the device still transmits it.
                r = round(n / 100, 2)
                if r > 0:
                    result[key] = r

            elif key == "temp":
                # Other models: temperature encoded as n-100
                t = n - 100
                if t > 10:
                    result[key] = round(t, 1)

            elif key == "accum_charge_cap":
                result[key] = round(n / 1000, 3)

        if "ah_remaining" in result and self._battery_capacity > 0:
            result["soc"] = min(100.0, round(result["ah_remaining"] / self._battery_capacity * 100, 1))

        return result
