# Junctek BLE Battery Monitor

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

A Home Assistant custom integration for Junctek BLE battery monitors that works with **ESPHome Bluetooth proxies** and any other HA-managed Bluetooth adapter — not just a Bluetooth radio physically attached to the HA host.

## Why this instead of the addon?

The [Junctek addon](https://github.com/Tsjippy/ha-addons/tree/main/Junctek) talks to Bluetooth directly via the host's BlueZ stack. That means it only sees devices reachable by a USB/built-in Bluetooth radio on the machine running HA. This integration uses Home Assistant's Bluetooth integration layer, so it transparently works with:

- Local Bluetooth adapters on the HA host
- [ESPHome Bluetooth proxies](https://esphome.io/components/bluetooth_proxy.html)
- Any other HA-compatible Bluetooth proxy

## Sensors

| Sensor | Unit | Notes |
|--------|------|-------|
| Voltage | V | Filtered below 80 % of nominal |
| Current | A | Negative = charging |
| Power | W | Negative = charging |
| Temperature | °C | |
| State of Charge | % | Calculated from remaining capacity |
| Remaining Capacity | Ah | |
| Remaining Time | min | |
| Accumulated Charge | Ah | |
| Discharged Today | kWh | Daily total from device |
| Charged Today | kWh | Daily total from device |
| Last Message | timestamp | |

## Requirements

- Home Assistant 2023.1 or later
- The HA **Bluetooth** integration enabled
- At least one Bluetooth source visible to HA (local adapter or ESPHome proxy)
- Your Junctek device's MAC address

## Installation

### Via HACS (recommended)

1. In HACS, go to **Integrations** → three-dot menu → **Custom repositories**
2. Add `https://github.com/2bitoperations/junctek-ble-proxy-compatible-ha-integration` with category **Integration**
3. Click **Download**
4. Restart Home Assistant

### Manual

Copy `custom_components/junctek_ble/` into your HA config's `custom_components/` directory and restart.

## Configuration

After installation, go to **Settings → Devices & Services → Add Integration** and search for **Junctek BLE Battery Monitor**.

The config flow will show Bluetooth devices already seen by HA in a dropdown. If your device isn't listed yet, enter its MAC address manually (`AA:BB:CC:DD:EE:FF`).

**Battery Capacity** and **Nominal Voltage** are used only for State of Charge calculation — they don't affect other sensor values.

## Connection behaviour

The integration registers for Bluetooth advertisements from your device's address. When the device is seen (directly or through a proxy), it connects via GATT and subscribes to characteristic `0000fff1-0000-1000-8000-00805f9b34fb` for push notifications. It reconnects automatically on disconnect.
