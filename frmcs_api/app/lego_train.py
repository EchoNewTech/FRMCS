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

    def reset_sensors(self):
        """Resetuje sensor powiązany z konkretnym pociągiem."""
        try:
            if hasattr(self, 'lsm') and self.lsm:
                # Jeśli Twoja biblioteka sensora ma metodę kalibracji/resetu:
                # self.lsm.calibrate() 
                
                # Jeśli nie, zrób prosty restart instancji (zależnie od tego, jak inicjujesz):
                print(f"[{self.name}] Wykonuję reset akcelerometru...")
                # Tu wpisz logikę, która czyści bufor Twojego sensora
            else:
                print(f"[{self.name}] Brak aktywnego sensora do resetu.")
        except Exception as e:
            print(f"[{self.name}] Błąd podczas resetu sensora: {e}")

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
        if self.detector:
            self.detector.process_notification(data)

    async def send_speed(self, speed: int):
        if not self.is_connected: return
        try:
            self.speed = max(-80, min(80, speed))
            speed_val = int(self.speed).to_bytes(1, byteorder="little", signed=True)[0]
            payload = bytearray([0x08, 0x00, 0x81, 0x00, 0x11, 0x51, 0x00, speed_val])
            
            # Timeout set to prevent hanging, but we do NOT drop connection on a single failure
            await self.client.write_gatt_char(LEGO_HUB_CHARACTERISTIC, payload)
            return True

            '''await asyncio.wait_for(
                self.client.write_gatt_char(LEGO_HUB_CHARACTERISTIC, payload),
                timeout=0.5
            )'''
        except Exception:
            # Silent failure: BLE dropped a packet. We log it gently without forcing a full disconnect.
            print(f"[{self.name}] Warning: Speed command timed out (BLE lag).")

    async def stop(self):
        await self.send_speed(0)
