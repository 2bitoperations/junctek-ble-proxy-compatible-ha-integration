# Open Items

## Potential improvements

- SoC by chemistry: the Junctek app offers different SOC curves (LiFePO4, NMC, lead-acid). We currently use a flat linear capacity calculation. Worth investigating if the device itself transmits a chemistry-corrected SOC in `d0` (cur_soc), and if so, what the encoding is.
- `e6` / `e7` (full_charge_volt, zero_charge_volt) are parsed but not exposed as sensors. May be useful for diagnostics.
- Multiple device instances: not tested with more than one BTG656 on the same HA instance.

## Resolved (kept for context)

- ~~CRC validation missing~~ → added in 1.0.8
- ~~HA startup hang (~6 min)~~ → fixed in 1.0.8 by switching watchdog to `async_create_background_task`
- ~~Temperature reporting ~70°C~~ → d7 misidentified as temperature; fixed across 1.0.9–1.0.11; see PROTOCOL.md
- ~~`discharge`/`charge` sensors broken in energy dashboard~~ → changed to `TOTAL_INCREASING` in 1.0.8
