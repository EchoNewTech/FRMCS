import asyncio
from bleak import BleakScanner

async def scan_ble():
    print("Skanowanie przez 10 sekund...\n")

    devices = await BleakScanner.discover(timeout=10)

    for device in devices:
        print(f"Nazwa:   {device.name}")
        print(f"Adres:   {device.address}")
        print("-" * 40)

asyncio.run(scan_ble())