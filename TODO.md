# Open Items

## Potential improvements

- "current" at odds with "power" sign-wise. when battery is charging, current is negative, but power is positive. discharging = the reverse. make these consistent.
- `b0` (device preset capacity) is parsed by the device but not by our integration. If we read it from packets we could auto-populate battery capacity instead of requiring user configuration. `b0` tag byte has a non-decimal hex char so it's not currently in PARAMS and would need explicit addition.
- `e6` / `e7` (full_charge_volt, zero_charge_volt) are parsed but not exposed as sensors. May be useful for diagnostics.
- Multiple device instances: not tested with more than one BTG656 on the same HA instance.

## Confirmed non-issues

- **No battery chemistry curves** — APK analysis (KHF, KG, KL pages) shows no chemistry/type selector. SOC is linear on all device models: `d2 / b0 × 100%`. Our linear implementation is correct.
- **d0 is not SOC** — on KL/BTG devices `d0` is relay/output state (`"00"`=on, `"99"`=off, protection states). Relabelled in const.py. Not displayed by the integration.

## Resolved (kept for context)

- ~~CRC validation missing~~ → added in 1.0.8
- ~~HA startup hang (~6 min)~~ → fixed in 1.0.8 by switching watchdog to `async_create_background_task`
- ~~Temperature reporting ~70°C~~ → d7 misidentified as temperature; fixed across 1.0.9–1.0.11; see PROTOCOL.md
- ~~`discharge`/`charge` sensors broken in energy dashboard~~ → changed to `TOTAL_INCREASING` in 1.0.8
