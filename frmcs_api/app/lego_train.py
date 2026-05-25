import asyncio
from bleak import BleakClient
from app.sensor import ColorDetector
from app.constants import LEGO_HUB_CHARACTERISTIC

ble_lock = asyncio.Lock()

class LegoTrain:
    def __init__(self, name: str, mac: str, train_type: str = "standard"):
        self.name, self.mac, self.train_type = name, mac, train_type
        self.client, self.speed, self.detector = None, 0, None
        # FIX: telemetry_url initialized here instead of externally in app.py
        self.rgb, self.section, self.telemetry_url = {"r": 0, "g": 0, "b": 0}, "DISCONNECTED", ""

    @property
    def is_connected(self):
        return self.client is not None and self.client.is_connected

    async def connect(self, dispatcher=None):
        if self.is_connected: return
        async with ble_lock:
            try:
                self.client = BleakClient(self.mac)
                await self.client.connect(timeout=20.0)
                self.detector = ColorDetector(self, dispatcher)
                await self.client.start_notify(LEGO_HUB_CHARACTERISTIC, self.notification_handler)
                # Query attached I/O to trigger sensor discovery
                await self.client.write_gatt_char(LEGO_HUB_CHARACTERISTIC, bytearray([0x05, 0x00, 0x01, 0x01, 0x05]))
                self.section = "INITIALIZING"
                print(f"[{self.name}] Bluetooth link established. Waiting for sensor...")
            except Exception as e:
                self.client = None
                raise e

    async def disconnect(self):
        self.detector = None
        if self.is_connected:
            try:
                await self.send_speed(0)
                await self.client.disconnect()
            except: pass
        self.client, self.section = None, "DISCONNECTED"

    def notification_handler(self, sender, data):
        # FIX: Bleak fires this on a background thread, NOT the asyncio event loop thread.
        # call_soon_threadsafe safely schedules process_notification (a sync callable)
        # onto the event loop thread, so asyncio.create_task() calls inside it work correctly.
        if self.detector:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(self.detector.process_notification, data)

    async def send_speed(self, speed: int):
        if not self.is_connected: return
        async with ble_lock:
            try:
                self.speed = max(-100, min(100, speed))
                speed_val = int(self.speed).to_bytes(1, byteorder="little", signed=True)[0]
                payload = bytearray([0x08, 0x00, 0x81, 0x00, 0x11, 0x51, 0x00, speed_val])
                await asyncio.wait_for(
                    self.client.write_gatt_char(LEGO_HUB_CHARACTERISTIC, payload),
                    timeout=0.5
                )
            except Exception:
                print(f"[{self.name}] Warning: Speed command timed out (BLE lag).")

    async def stop(self):
        await self.send_speed(0)
