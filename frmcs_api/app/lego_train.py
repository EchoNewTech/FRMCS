import asyncio
from bleak import BleakClient
from app.sensor import ColorDetector
from app.constants import LEGO_HUB_CHARACTERISTIC

ble_lock = asyncio.Lock()

class LegoTrain:
    def __init__(self, name: str, mac: str, train_type: str = "standard"):
        self.name, self.mac, self.train_type = name, mac, train_type
        self.client, self.speed, self.detector = None, 0, None
        self.rgb, self.section = {"r": 0, "g": 0, "b": 0}, "DISCONNECTED"

    @property
    def is_connected(self):
        # BleakClient może istnieć, ale nie być połączony - to musimy sprawdzać
        return self.client is not None and self.client.is_connected

    async def connect(self, dispatcher=None):
        if self.is_connected: return
        async with ble_lock:
            print(f"[{self.name}] Connecting to {self.mac}...")
            for attempt in range(3):
                try:
                    self.client = BleakClient(self.mac)
                    await self.client.connect(timeout=20.0)
                    
                    # Po połączeniu od razu startujemy powiadomienia
                    await self.client.start_notify(LEGO_HUB_CHARACTERISTIC, self.notification_handler)
                    await asyncio.sleep(1.0)
                    
                    self.detector = ColorDetector(self, dispatcher)
                    await self.detector.setup_sensor()
                    
                    self.section = "DRIVING"
                    print(f"[{self.name}] Connected successfully.")
                    break
                except Exception as e:
                    print(f"[{self.name}] Attempt {attempt + 1} failed: {e}")
                    if self.client:
                        await self.client.disconnect()
                    self.client = None # CZYŚCIMY, żeby is_connected było False
                    if attempt == 2:
                        self.section = "ERROR"
                        raise e
                    await asyncio.sleep(2)

    async def disconnect(self):
        self.detector = None
        if self.is_connected:
            try:
                await self.send_speed(0)
                await self.client.disconnect()
            except:
                pass
        self.client, self.section = None, "DISCONNECTED"

    def notification_handler(self, sender, data):
        if self.detector:
            self.detector.process_notification(data)

    async def send_speed(self, speed: int):
        if not self.is_connected: return
        self.speed = max(-100, min(100, speed))
        speed_val = int(self.speed).to_bytes(1, byteorder="little", signed=True)[0]
        payload = bytearray([0x08, 0x00, 0x81, 0x00, 0x11, 0x51, 0x00, speed_val])
        await self.client.write_gatt_char(LEGO_HUB_CHARACTERISTIC, payload)

    async def stop(self):
        await self.send_speed(0)
