#!/usr/bin/env python3
"""
Connect to a specific BLE device, dump all services/characteristics,
and capture raw notifications from every notify-capable characteristic.

Usage:
    python3 probe_device.py <MAC_ADDRESS>
"""

import asyncio
import sys
from bleak import BleakClient, BleakScanner

NOTIFY_SECONDS = 10   # how long to listen on each notifiable characteristic


async def main(address: str):
    # First resolve the device via scan (required by some BlueZ versions)
    print(f"Scanning to resolve {address} ...")
    device = await BleakScanner.find_device_by_address(address, timeout=15)
    if device is None:
        print(f"ERROR: {address} not found during scan. Is it powered on and nearby?")
        sys.exit(1)

    print(f"Found: {device.name or '(no name)'}  {device.address}\n")

    client = BleakClient(device, timeout=20)
    try:
        await client.connect()
        print(f"Connected: {client.is_connected}\n")
        print("=" * 60)
        print("SERVICE / CHARACTERISTIC MAP")
        print("=" * 60)

        notifiable = []   # (char_uuid, description) pairs

        for service in client.services:
            print(f"\nService  {service.uuid}")
            if service.description:
                print(f"         ({service.description})")

            for char in service.characteristics:
                props = ", ".join(char.properties)
                print(f"  Char   {char.uuid}  [{props}]")
                if char.description:
                    print(f"           ({char.description})")

                if "read" in char.properties:
                    try:
                        val = await client.read_gatt_char(char.uuid)
                        print(f"           read → hex:{val.hex()}  raw:{bytes(val)!r}")
                    except Exception as e:
                        print(f"           read → error: {e}")

                if "notify" in char.properties or "indicate" in char.properties:
                    notifiable.append((char.uuid, char.description or ""))

        print("\n" + "=" * 60)
        print(f"CAPTURING NOTIFICATIONS  ({NOTIFY_SECONDS}s per characteristic)")
        print("=" * 60)

        for char_uuid, desc in notifiable:
            print(f"\nSubscribing to {char_uuid}  ({desc or 'no description'})")
            captured = []

            def make_handler(uuid):
                def handler(_, value):
                    raw = bytes(value)
                    pairs = " ".join(raw.hex()[i:i+2] for i in range(0, len(raw.hex()), 2))
                    print(f"  [{uuid[:8]}]  hex: {pairs}")
                    print(f"             raw: {raw!r}")
                    captured.append(raw)
                return handler

            try:
                await client.start_notify(char_uuid, make_handler(char_uuid))
                await asyncio.sleep(NOTIFY_SECONDS)
                await client.stop_notify(char_uuid)
                if not captured:
                    print("  (no notifications received in window)")
            except Exception as e:
                print(f"  subscribe error: {e}")

    finally:
        # EOFError on disconnect is benign (device closed first) — swallow it.
        try:
            await client.disconnect()
        except Exception:
            pass

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <MAC_ADDRESS>")
        sys.exit(1)
    try:
        asyncio.run(main(sys.argv[1].upper()))
    except KeyboardInterrupt:
        print("\nAborted.")
