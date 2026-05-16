from bleak import BleakClient

LEGO_HUB_CHARACTERISTIC = "00001624-1212-efde-1623-785feabcd123"

class LegoTrain:
    def __init__(self, name, mac):
        self.name = name
        self.mac = mac
        self.client = None
        self.speed = 0
        self.detector = None
        self.is_virtual = False

    def notification_handler(self, sender, data):
        """Metoda wywoływana, gdy przyjdzie jakakolwiek paczka danych z Huba."""
        if self.detector:
            self.detector.process_notification(data)

    async def connect(self):
        """Łączy się z pociągiem przez Bluetooth. Zwraca True jeśli połączenie się powiodło."""
        try:
            print(f"Łączenie z {self.name} ({self.mac})...")
            self.client = BleakClient(self.mac)
            await self.client.connect()
            await self.client.start_notify(LEGO_HUB_CHARACTERISTIC, self.notification_handler)
            print(f"Połączono z {self.name}!")
            return True
        except Exception as e:
            print(f"Błąd połączenia z {self.name}: {e}")
            return False

    async def set_speed(self, target_speed):
        """Ustawia prędkość pociągu. Blokada: tylko jeśli połączony. Zwraca True jeśli komenda została wysłana."""
        self.speed = max(-100, min(100, target_speed))
        if self.is_virtual:
            return True
        
        if not self.client or not self.client.is_connected:
            return False

        try:
            speed_val = int(self.speed).to_bytes(1, byteorder='little', signed=True)[0]
            payload = bytearray([0x08, 0x00, 0x81, 0x00, 0x11, 0x51, 0x00, speed_val])
            await self.client.write_gatt_char(LEGO_HUB_CHARACTERISTIC, payload)
            return True
        except Exception as e:
            print(f"Błąd komunikacji z {self.name}: {e}")
            return False

    async def stop(self):
        """Zatrzymuje pociąg. Blokada: tylko jeśli połączony. Zwraca True jeśli komenda została wysłana."""
        if not self.client or not self.client.is_connected:
            return False
        self.speed = 0
        return await self.set_speed(0)
