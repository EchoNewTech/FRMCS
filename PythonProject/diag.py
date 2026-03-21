import asyncio
from bleak import BleakScanner

async def run():
    print("Szukam urządzeń BLE")
    devices = await BleakScanner.discover()
    
    if not devices:
        print("Nie znaleziono żadnych urządzeń. Sprawdź czy Bluetooth w laptopie jest włączony!")
        return

    for d in devices:
        # Jeśli urządzenie nie ma nazwy, wyświetlimy 'Brak nazwy'
        name = d.name if d.name else "Brak nazwy"
        print(f"Nazwa: {name} | Adres: {d.address}")

asyncio.run(run())
