# Junctek BLE Protocol Notes

Everything known about the binary BLE protocol, derived from:
- Live BLE packet capture
- Reverse engineering the Junce Home 1.6.5 APK (`app-service.js`, 3.8 MB minified JS)
- Trial and error against live HA sensor data

---

## BLE Characteristic

GATT service / characteristic UUID: `0000fff1-0000-1000-8000-00805f9b34fb`

The integration subscribes to notifications on this characteristic. Data arrives as push notifications; no polling write is needed.

---

## Frame Format (binary protocol)

Devices that use the binary protocol (KHF, KG-F, KL/BTG656, and others) emit BLE notifications that may contain one or more frames, or raw bytes with no framing.

### Framed packets

```
BB  [tag] [value...] [checksum] EE
```

- `0xBB` = frame start
- `0xEE` = frame end
- One or more **tag bytes** (e.g. `0xD4` = `"d4"`)
- Zero or more **BCD value bytes** preceding each tag (in transmission order — reversed during parse)
- `checksum` = second-to-last byte (before `0xEE`)
- A single BLE notification can carry multiple concatenated frames

### Checksum algorithm

```python
n = sum(frame[:-2]) % 100          # sum all bytes except checksum + EE
expected = ((n // 10) << 4) | (n % 10)   # pack as BCD byte
assert frame[-2] == expected
```

Equivalently: take the decimal sum of all bytes in the frame (including `0xBB`, excluding checksum and `0xEE`), mod 100, then BCD-encode it into one byte (high nibble = tens digit, low nibble = units digit).

### Parser logic

1. Split notification into `BB..EE` frames (see `_split_frames`).
2. Validate each frame's checksum. Frames that fail are logged as `BAD:` and discarded.
3. For each valid frame, hex-encode it: `"bb01158ad417ee"`.
4. Split into two-char byte strings and **reverse** the list.
5. Iterate the reversed list. When a byte is in `PARAMS_VALUES` (the set of known tag hex codes), collect all following bytes whose two-hex-char representation is all-decimal-digits (`"00"`–`"09"`, `"10"`–`"99"`, etc. — BCD value bytes). Prepend each collected byte to build the decimal string (so the final integer is MSB-first).

**Why reversed?** The device emits values before their tag in the byte stream. Reversing puts the tag first in iteration order so we can collect the value bytes that immediately follow.

**Valid value bytes:** only bytes whose hex representation is all decimal digits (`00`, `01`, …, `99`) are BCD. Bytes with any hex digit A–F (`a0`, `b1`, `c0`, etc.) stop value collection — most of these are tag bytes themselves.

---

## Tag Bytes and Decoding

All confirmed from APK analysis of `app-service.js` (function `KHFstrToObj`, display templates for KHF / KG / KL pages).

| Tag (hex) | Key              | Formula          | Unit | Notes |
|-----------|------------------|------------------|------|-------|
| `c0`      | voltage          | n / 100          | V    | Filtered: only accepted if > 5.0 V |
| `c1`      | current          | n / 100          | A    | Sign inverted when `_charging` is True |
| `d0`      | relay_state      | (raw)            | —    | Relay/output control on KL/BTG devices: `"00"`=on, `"99"`=off, `"01"`/`"02"`=protection active. Not displayed. |
| `d1`      | dir_of_current   | `"01"` = charging| —    | Sets `_charging` flag |
| `d2`      | ah_remaining     | n / 1000         | Ah   | Also used to compute SOC |
| `d3`      | discharge        | n / 100000       | kWh  | Clears `_charging` flag |
| `d4`      | charge           | n / 100000       | kWh  | Sets `_charging` flag |
| `d5`      | accum_charge_cap | n / 1000         | Ah   | |
| `d6`      | mins_remaining   | n                | min  | Time to full (charging) or to empty (discharging) |
| `d7`      | int_resistance   | n / 100          | mΩ   | Internal resistance — labelled "IntRes" in app on KG-F page; KL/BTG656 transmits but does not display it |
| `d8`      | power            | n / 100          | W    | Sign inverted when not `_charging` |
| `d9`      | temp             | n − 100          | °C   | External temperature probe; only transmitted when probe is physically connected |
| `e6`      | full_charge_volt | (raw)            | —    | Not currently displayed |
| `e7`      | zero_charge_volt | (raw)            | —    | Not currently displayed |

### Other fields seen in APK but NOT currently in PARAMS

| Field | Meaning | Notes |
|-------|---------|-------|
| `b0`  | Device preset battery capacity | n / 10 = Ah. Stored on device; written via `"9ab0" + value + "b0"`. The app reads this back to display the configured capacity. Our integration uses a separately user-configured capacity instead. |
| `b1`  | Over-temperature protection threshold | Setting (n − 100 = °C). Written via `"9ab1" + value + "b1"` command prefix. Not a live sensor reading. |
| `b4`  | Low-temperature protection threshold | Written via `"9ad99ab4" + value + "b4"`. |
| `b2`  | Voltage alignment offset | Written via `"9ac09ab2" + value + "b2"`. |
| `c4`  | Device address/ID | Raw value displayed as integer. |
| `f7`  | Temperature unit flag | `"01"` = Fahrenheit, `"00"` = Celsius. Config setting. |

---

## Device Pages and Model Routing

The Junctek app routes devices to different pages based on BLE name prefix:

| Page     | Device names     | Notable differences |
|----------|-----------------|---------------------|
| KHF      | BTG, BTH        | Binary protocol; `KHFstrToObj` parser |
| KG       | KG-F            | Binary protocol; shows `d7` as Internal Resistance |
| KL       | KL-F, **BTG656**| Binary protocol; shows `d9` as "External Temperature" only |
| BLF      | BL-F            | ASCII text protocol (`:A=val,...\r\n`) |
| KMF      | KM-F            | ASCII text protocol variant |

The **BTG656** is treated as a KL device. Key consequence: the KL page only shows temperature when an external probe is connected (d9). There is no internal NTC readout on the display page.

---

## Temperature — What the App Actually Does

### KL page (BTG656)

```
label:   exttemp  ("External Temperature")
display: dataObject.d9 − 100   if d9 present and not "00" or "79"
         "--"                   otherwise
```

- `"00"` = no sensor / probe absent
- `"79"` = sensor error
- No temperature is shown when no probe is connected.

### Settings panel (all devices)

```
label:   OverTemperatureProtection
display: dataObject.b1 − 100   (the threshold, not a live reading)
```

### KG page

```
label:   IntRes  ("Internal Resistance")
display: dataObject.d7 / 100   mΩ
```

### Why d7 ≠ temperature

In the live 200-packet log from a BTG656, `d7` values ranged from 1492 to 3846 and tracked **perfectly with `d6`** (ratio ≈ 0.177 consistently). `d7 / 100` happened to fall in a plausible temperature range (14.9–38.5°C) during one test period, which caused it to be mis-identified as temperature in early versions.

The d6/d7 correlation is explained by the fact that both track the solar charge cycle: as solar charging increases SOC, remaining time (d6) increases, and internal resistance (d7/100 mΩ) changes proportionally with state-of-charge. The apparent "daily temperature cycle" in d7 is actually SOC rising and falling with sun.

---

## Charging State Tracking

The integration tracks a `_charging` boolean to correctly sign current and power:

- `d4` (charge) received → `_charging = True`
- `d3` (discharge) received → `_charging = False`
- `d1` (dir_of_current) = `"01"` → `_charging = True`

Current is negated when charging. Power is negated when discharging.

---

## SOC Calculation

Computed by the integration (not from device):

```python
soc = min(100.0, round(ah_remaining / battery_capacity * 100, 1))
```

`battery_capacity` is user-configured at setup (Ah). Device sends `d2` (ah_remaining).

**No chemistry curves exist in this protocol.** The app has no battery chemistry / type selection (LiFePO4, NMC, lead-acid). SOC is purely linear across all device models. The device itself stores a preset capacity in `b0` (n/10 Ah), which it uses for its own remaining-time calculation; the integration duplicates this as a user configuration field.

---

## Reconnection and Watchdog

- The integration subscribes to HA's Bluetooth advertisement callbacks for the device address.
- On each advertisement event, if not already connected, it connects via GATT and subscribes to notifications.
- A background watchdog task (`async_create_background_task`) checks every 60 seconds: if no data has arrived in the past 120 seconds, it disconnects to force a reconnect cycle.
- **Critical:** the watchdog must be a background task. Using a tracked task (`async_create_task`) caused HA to wait for it during startup, producing a ~6-minute boot hang.

---

## Packet Log

A rolling 200-entry diagnostic buffer is kept in `coordinator._packet_log`. Each entry is:

- `OK:<hex>` — frame passed CRC
- `BAD:<hex>` — frame failed CRC (discarded)
- `RAW:<hex>` — notification had no `BB..EE` framing; attempted raw parse

The log is exposed as the `packet_log` extra attribute on the "Last Raw Packet" diagnostic sensor.

---

## Fix History

| Version | Change |
|---------|--------|
| 1.0.8   | Watchdog moved to background task — fixed ~6-minute HA startup hang |
| 1.0.8   | `discharge`/`charge` sensors changed from `MEASUREMENT` to `TOTAL_INCREASING` |
| 1.0.8   | CRC validation and packet log added |
| 1.0.9   | `d7` moved to separate `temp_d7` key so `d9` could take priority for temperature |
| 1.0.10  | Added 55°C upper bound filter on `d7` to drop bogus high values |
| 1.0.11  | `d7` correctly identified as internal resistance (not temperature) via APK analysis; temperature sensor now only uses `d9`; "Internal Resistance" diagnostic sensor added |

---

## APK Analysis Notes

Source: `Junce Home 1.6.5` APK, decompiled with jadx, primary logic in:

```
resources/com.juntek.platform.apk/assets/apps/__UNI__D0FA0D1/www/app-service.js
```

Key functions:
- `KHFstrToObj` — binary frame parser (KHF/BTG/BTH devices)
- `strToObj` — ASCII text packet parser (BLF/KMF devices) and binary parser variant for KG
- `strAddSpace` — converts raw hex notification to comma-separated byte pairs (binary) or ASCII (text protocol)
- `hexToString` — hex → ASCII, used by text-protocol pages

The binary parser iterates the comma-split hex bytes in reverse, groups BCD digit bytes before each non-BCD tag byte, reverses the digit string to get the value integer.
