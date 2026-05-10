from bleak import BleakClient

LEGO_HUB_CHARACTERISTIC = "00001624-1212-efde-1623-785feabcd123"

class LegoTrain:
    def __init__(self, name, mac):
        self.name = name
        self.mac = mac
        self.client = None
        self.light_on = False
        self.speed = 0

    async def connect(self):
        try:
            print(f"Łączenie z {self.name} ({self.mac})...")
            self.client = BleakClient(self.mac)
            await self.client.connect()
            print(f"Połączono z {self.name}!")
            return True
        except Exception as e:
            print(f"Błąd połączenia z {self.name}: {e}")
            return False

    async def send_speed(self, target_speed):
        # Blokada: tylko jeśli połączony
        if not self.client or not self.client.is_connected:
            return False

        try:
            self.speed = max(-100, min(100, target_speed))
            speed_val = int(self.speed).to_bytes(1, byteorder='little', signed=True)[0]
            payload = bytearray([0x08, 0x00, 0x81, 0x00, 0x11, 0x51, 0x00, speed_val])
            await self.client.write_gatt_char(LEGO_HUB_CHARACTERISTIC, payload)
            return True
        except Exception as e:
            print(f"Błąd komunikacji z {self.name}: {e}")
            return False

    async def stop(self):
        if not self.client or not self.client.is_connected:
            return False
        self.speed = 0
        return await self.send_speed(0)

    async def set_light(self, brightness):
        if not self.client or not self.client.is_connected:
            return False
        try:
            brightness = max(0, min(100, int(brightness)))
            payload = bytearray([0x08, 0x00, 0x81, 0x01, 0x11, 0x51, 0x00, brightness])
            await self.client.write_gatt_char(LEGO_HUB_CHARACTERISTIC, payload)
            self.light_on = brightness > 0
            return True
        except Exception as e:
            print(f"Błąd świateł {self.name}: {e}")
            return False