from bleak import BleakClient
import time



LEGO_HUB_CHARACTERISTIC = "00001624-1212-efde-1623-785feabcd123"


class LegoTrain:
    def __init__(self, name, mac, start_pos=0):
        self.name = name
        self.mac = mac
        self.client = None
        self.speed = 0
        self.pos = float(start_pos)
        self.last_update = time.time()

    async def connect(self):
        if self.client and self.client.is_connected:
            return

        print(f"Łączenie z {self.name}...")
        self.client = BleakClient(self.mac)
        await self.client.connect()
        print(f"{self.name} connected")

    async def send_speed(self, speed):
        self.speed = max(-80, min(80, speed))

        speed_val = int(self.speed).to_bytes(1, byteorder='little', signed=True)[0]
        payload = bytearray([0x08, 0x00, 0x81, 0x00, 0x11, 0x51, 0x00, speed_val])

        await self.client.write_gatt_char(LEGO_HUB_CHARACTERISTIC, payload)

    async def stop(self):
        self.speed = 0
        await self.send_speed(0)
    
    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            print(f"{self.name} disconnected")

