import asyncio
from bleak import BleakClient

ADDRESS = "9C:9A:C0:18:86:E1"  # Adres MAC pociągu
UUID_LEGO = "00001624-1212-efde-1623-785feabcd123"  # Jedno dla wszystkich identyczne

class LegoTrainRemote:
    def __init__(self):
        self.client = None
        self.current_speed = 0

    async def connect(self):
        print(f"Łączenie z pociągiem {ADDRESS}...")
        self.client = BleakClient(ADDRESS)
        await self.client.connect()
        print("Połączono")

    async def set_speed(self, speed):
        # Stopnie prędkości
        if speed == 0:
            target_speed = 0
        elif 0 < speed < 40:
            target_speed = 40
        elif speed > 80:
            target_speed = 80
        elif speed < -80:
            target_speed = -80
        elif -40 < speed < 0:
            target_speed = -40
        else:
            target_speed = speed

        self.current_speed = target_speed

        speed_byte = self.current_speed & 0xFF

        # [Długość, HubID, Typ (WriteDirect), Port (00=A), Tryb, Subkomenda, Wartość]
        command = bytearray([0x08, 0x00, 0x81, 0x00, 0x11, 0x51, 0x00, speed_byte])

        try:
            await self.client.write_gatt_char(UUID_LEGO, command)
            print(f"Moc: {self.current_speed}%")
        except Exception as e:
            print(f"Błąd wysyłania: {e}")

    async def run_remote(self):
        await self.connect()
        print("\nINSTRUKCJA:")
        print("W - Zwiększ prędkość")
        print("S - Zmniejsz prędkość / Cofaj")
        print("Spacja - Nagłe STOP")
        print("Q - Wyjście")

        while True:
            cmd = await asyncio.to_thread(input, "Komenda: ")
            cmd = cmd.lower()

            if cmd == 'w':
                await self.set_speed(self.current_speed + 10)
            elif cmd == 's':
                await self.set_speed(self.current_speed - 10)
            elif cmd == ' ':
                await self.set_speed(0)
            elif cmd == 'q':
                await self.set_speed(0)
                break
            else:
                print("Nieznana komenda!")

        await self.client.disconnect()
        print("Rozłączono.")


if __name__ == "__main__":
    remote = LegoTrainRemote()
    try:
        asyncio.run(remote.run_remote())
    except Exception as e:
        print(f"Wystąpił błąd: {e}")
