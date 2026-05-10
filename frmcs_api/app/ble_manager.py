from bleak import BleakClient


ADDRESS = "9C:9A:C0:18:86:E1"
UUID_LEGO = "00001624-1212-efde-1623-785feabcd123"


class BLEManager:
    def __init__(self):
        self.client = None
        self.current_speed = 0

    async def connect(self):
        if self.client and self.client.is_connected:
            print("Już połączony")
            return

        print("Łączenie BLE...")
        self.client = BleakClient(ADDRESS)
        await self.client.connect()
        print("Połączono")

    async def set_speed(self, speed: int):
        speed_byte = speed & 0xFF
        command = bytearray([0x08, 0x00, 0x81, 0x00, 0x11, 0x51, 0x00, speed_byte])
        await self.client.write_gatt_char(UUID_LEGO, command)
