DOMAIN = "junctek_ble"

CHARACTERISTIC_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"

CONF_BATTERY_CAPACITY = "battery_capacity"
CONF_BATTERY_VOLTAGE = "battery_voltage"

# Maps human-readable param names to the two-hex-char codes the device embeds in notifications.
PARAMS: dict[str, str] = {
    "voltage":          "c0",
    "current":          "c1",
    "relay_state":      "d0",   # relay/output state on KL/BTG devices; meaning varies by model
    "dir_of_current":   "d1",
    "ah_remaining":     "d2",
    "discharge":        "d3",
    "charge":           "d4",
    "accum_charge_cap": "d5",
    "mins_remaining":   "d6",
    # d7: internal resistance in mΩ (value / 100 = mΩ); used as IntRes on KG-F and related devices
    "int_resistance":   "d7",
    "power":            "d8",
    # d9: external temperature probe in °C (value - 100); only present when probe is physically connected
    "temp":             "d9",
    "full_charge_volt": "e6",
    "zero_charge_volt": "e7",
}

PARAMS_KEYS   = list(PARAMS.keys())
PARAMS_VALUES = list(PARAMS.values())
