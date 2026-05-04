DOMAIN = "junctek_ble"

CHARACTERISTIC_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"

CONF_BATTERY_CAPACITY = "battery_capacity"
CONF_BATTERY_VOLTAGE = "battery_voltage"

# Maps human-readable param names to the two-hex-char codes the device embeds in notifications.
PARAMS: dict[str, str] = {
    "voltage":          "c0",
    "current":          "c1",
    "cur_soc":          "d0",
    "dir_of_current":   "d1",
    "ah_remaining":     "d2",
    "discharge":        "d3",
    "charge":           "d4",
    "accum_charge_cap": "d5",
    "mins_remaining":   "d6",
    # d7: temperature at n/100 scale (BTG656 and similar models)
    "temp_d7":          "d7",
    "power":            "d8",
    # d9: temperature at n-100 scale (other models)
    "temp":             "d9",
    "full_charge_volt": "e6",
    "zero_charge_volt": "e7",
}

PARAMS_KEYS   = list(PARAMS.keys())
PARAMS_VALUES = list(PARAMS.values())
