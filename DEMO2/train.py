import asyncio
from bleak import BleakClient

LEGO_HUB_CHARACTERISTIC = "00001624-1212-efde-1623-785feabcd123"

class LegoTrain:
    def __init__(self, name, mac):
        self.name = name
        self.mac = mac
        self.client = None
        self.speed = 0
        self.detector = None
        # Zabezpieczenie przed próbą podwójnego łączenia do tego samego huba
        self.is_connecting = False 

    def notification_handler(self, sender, data):
        """Metoda wywoływana, gdy przyjdzie jakakolwiek paczka danych z Huba."""
        if self.detector:
            self.detector.process_notification(data)

    async def connect_to_device(self, device):
        """Łączy się bezpośrednio, korzystając z namierzonego już przez skaner obiektu."""
        if self.is_connecting or (self.client and self.client.is_connected):
            return True
            
        self.is_connecting = True
        try:
            print(f"[{self.name}] Próba połączenia z hubem...")
            self.client = BleakClient(device)
            # Dajemy mu 15 sekund na dogadanie się z hubem
            await self.client.connect(timeout=15.0)
            await self.client.start_notify(LEGO_HUB_CHARACTERISTIC, self.notification_handler)
            print(f"[{self.name}] SUKCES! Pociąg połączony.")
            self.is_connecting = False
            return True
        except Exception as e:
            print(f"[{self.name}] Połączenie zerwane: {e}")
            if self.client:
                try:
                    await self.client.disconnect()
                except:
                    pass
            self.client = None
            self.is_connecting = False
            return False

    async def set_speed(self, target_speed):
        """Ustawia prędkość pociągu. Blokada: tylko jeśli połączony."""
        self.speed = max(-100, min(100, target_speed))
        
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
        """Zatrzymuje pociąg. Blokada: tylko jeśli połączony."""
        if not self.client or not self.client.is_connected:
            return False
        self.speed = 0
        return await self.set_speed(0)