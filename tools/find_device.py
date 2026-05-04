#!/usr/bin/env python3
"""
Scan for Junctek BLE battery monitors and identify their MAC address.

Stages:
  1. Passive 15-second scan — lists every advertising device with RSSI.
     Devices that advertise the Junctek service UUID are flagged immediately.
  2. Connection attempt on each candidate — checks for characteristic
     0000fff1-0000-1000-8000-00805f9b34fb.
  3. Data validation — subscribes for 8 seconds and checks that incoming
     notifications parse as Junctek data (at least one known parameter code).
"""

import asyncio
import sys
from bleak import BleakClient, BleakScanner

CHAR_UUID    = "0000fff1-0000-1000-8000-00805f9b34fb"
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"

# Known field-tag bytes that appear inside Junctek notifications.
JUNCTEK_PARAM_CODES = {
    "c0", "c1",                         # voltage, current
    "d0", "d1", "d2", "d3", "d4",      # soc, direction, ah_remaining, discharge, charge
    "d5", "d6", "d7", "d8", "d9",      # accum_cap, mins_remaining, temp(n/100), power, temp(n-100)
    "e6", "e7",                         # full_charge_volt, zero_charge_volt
}

SCAN_SECONDS  = 15
DATA_WAIT_SEC = 8    # increased from 6 — some models send multi-code packets infrequently


def looks_like_junctek(data: bytes) -> bool:
    """Return True if the notification contains at least one known Junctek field code."""
    hex_str = data.hex()
    tokens  = [hex_str[i:i+2] for i in range(0, len(hex_str), 2)]
    return any(t in JUNCTEK_PARAM_CODES for t in tokens)


async def probe(device) -> str:
    """
    Connect, check for the characteristic, subscribe, and validate data.

    Uses manual connect/disconnect (not async-with) so that a benign
    EOFError on disconnect does not overwrite a successful result.

    Returns one of: "confirmed", "characteristic_only", "no_characteristic", "failed: <reason>"
    """
    client = BleakClient(device, timeout=15)
    outcome = "failed: never connected"

    try:
        await client.connect()

        char = None
        for svc in client.services:
            for c in svc.characteristics:
                if c.uuid.lower() == CHAR_UUID:
                    char = c
                    break

        if char is None:
            outcome = "no_characteristic"
        else:
            got_valid = asyncio.Event()
            got_any   = asyncio.Event()

            def handler(_, value):
                got_any.set()
                if looks_like_junctek(bytes(value)):
                    got_valid.set()

            try:
                await client.start_notify(CHAR_UUID, handler)
                try:
                    await asyncio.wait_for(got_valid.wait(), timeout=DATA_WAIT_SEC)
                    outcome = "confirmed"
                except asyncio.TimeoutError:
                    outcome = "characteristic_only (no valid data in window)" if not got_any.is_set() \
                              else "characteristic_only (data arrived but no known codes matched)"
            except Exception as e:
                outcome = f"failed: notify error: {e}"
            finally:
                try:
                    await client.stop_notify(CHAR_UUID)
                except Exception:
                    pass

    except Exception as e:
        outcome = f"failed: {e}"
    finally:
        # Disconnect errors (e.g. EOFError when device closed first) are benign — ignore them.
        try:
            await client.disconnect()
        except Exception:
            pass

    return outcome


async def main():
    print(f"Scanning {SCAN_SECONDS}s for all BLE devices...\n")
    print(f"{'ADDRESS':<20} {'RSSI':>5}  {'NAME':<30}  NOTE")
    print("-" * 75)

    seen: dict[str, tuple] = {}

    def on_device(device, adv):
        addr = device.address.upper()
        if addr in seen:
            return
        seen[addr] = (device, adv)

        uuids = [str(u).lower() for u in adv.service_uuids]
        flag  = "  ← SERVICE UUID MATCH" if SERVICE_UUID in uuids else ""
        name  = adv.local_name or device.name or ""
        rssi  = adv.rssi if adv.rssi is not None else "?"
        print(f"{addr:<20} {str(rssi):>5}  {name:<30}{flag}")

    async with BleakScanner(detection_callback=on_device):
        await asyncio.sleep(SCAN_SECONDS)

    print(f"\n{len(seen)} device(s) found.\n")

    service_matches = [
        (dev, adv) for dev, adv in seen.values()
        if SERVICE_UUID in [str(u).lower() for u in adv.service_uuids]
    ]

    if service_matches:
        candidates = service_matches
        print(f"{len(candidates)} device(s) advertise the Junctek service UUID — probing those.\n")
    else:
        print("No service-UUID matches. Probing all devices with RSSI ≥ -85...\n")
        candidates = [
            (dev, adv) for dev, adv in seen.values()
            if adv.rssi is not None and adv.rssi >= -85
        ]

    if not candidates:
        print("No candidates to probe. Is the monitor powered on and within ~5 m?")
        sys.exit(1)

    confirmed = []
    for dev, adv in candidates:
        name = adv.local_name or dev.name or "(no name)"
        print(f"Probing {dev.address}  ({name}) ...", end=" ", flush=True)
        result = await probe(dev)
        print(result)
        if result.startswith("confirmed") or result.startswith("characteristic_only"):
            confirmed.append((dev, adv, result))

    print()
    if confirmed:
        print("=" * 60)
        print("RESULT — use one of these MAC addresses in HA:")
        print("=" * 60)
        for dev, adv, result in confirmed:
            name   = adv.local_name or dev.name or "(no name)"
            status = "data validated ✓" if result == "confirmed" else result
            print(f"  {dev.address}  {name}  [{status}]")
        print()
        print("NOTE: if your battery is 12 V or 24 V, set battery_voltage accordingly")
        print("in the HA config flow — the default is 48 V and voltages below")
        print("80 % of that value are filtered out.")
    else:
        print("No Junctek device found. Check that it is powered and advertising.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAborted.")
