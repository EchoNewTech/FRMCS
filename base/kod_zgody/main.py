import asyncio
from lego_train import LegoTrain
from strowanie2 import control_loop
# Adresy MAC
EXPRESS_MAC = "9C:9A:C0:18:86:E1"
CARGO_MAC = "9C:9A:C0:1A:7A:AF"


async def main():
    express = LegoTrain("Express", EXPRESS_MAC, start_pos=0) # startowa pozycja 0
    cargo = LegoTrain("Cargo", CARGO_MAC, start_pos=20) # TODO startowa pozycja 20
    await express.connect()
    await asyncio.sleep(1)
    await cargo.connect()
    await asyncio.sleep(1)
    await control_loop(express, cargo)
    if express.client and express.client.is_connected:
        try:
            await express.stop()
        except:
            pass

    if cargo.client and cargo.client.is_connected:
        try:
            await cargo.stop()
        except:
            pass

    print("Koniec")

if __name__ == "__main__":
    asyncio.run(main())