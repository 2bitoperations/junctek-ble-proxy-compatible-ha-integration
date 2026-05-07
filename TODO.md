# Open Items

## Potential improvements

- `b0` read-back: could auto-populate battery capacity from the device instead of requiring user config. The `b0` tag byte contains a non-decimal hex char so it's not in PARAMS and would need explicit handling.
- `e6` / `e7` (full_charge_volt, zero_charge_volt) are parsed but not exposed as sensors. May be useful for diagnostics.
- Multiple device instances: not tested with more than one BTG656 on the same HA instance.
- `battery_voltage` config field is currently unused (no BLE write command exists for voltage range). Could be removed from the config flow to avoid confusion.

## Confirmed non-issues

- **No battery chemistry curves** — APK analysis (KHF, KG, KL pages) shows no chemistry/type selector. SOC is linear on all device models: `d2 / b0 × 100%`. Our linear implementation is correct.
- **d0 is not SOC** — on KL/BTG devices `d0` is relay/output state (`"00"`=on, `"99"`=off, protection states). Relabelled in const.py. Not displayed by the integration.

## Resolved (kept for context)

- ~~CRC validation missing~~ → added in 1.0.8
- ~~HA startup hang (~6 min)~~ → fixed in 1.0.8 by switching watchdog to `async_create_background_task`
- ~~Temperature reporting ~70°C~~ → d7 misidentified as temperature; fixed across 1.0.9–1.0.11; see PROTOCOL.md
- ~~`discharge`/`charge` sensors broken in energy dashboard~~ → changed to `TOTAL_INCREASING` in 1.0.8
- ~~current/power sign inconsistency~~ → fixed in 1.0.13; both negative = charging, positive = discharging
- ~~voltage always Unavailable~~ → fixed in 1.0.14–1.0.16; device requires initial `9aa9` poll (`bb9aa90cee`) to start transmitting c0
- ~~b0 capacity write missing~~ → fixed in 1.0.12; integration writes capacity to device on every connect
