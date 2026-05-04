import asyncio
from config import COLORS_CONFIG
from train import LEGO_HUB_CHARACTERISTIC

class ColorDetector:
    def __init__(self, train, dispatcher, port_id=0x01):
        self.train = train
        self.dispatcher = dispatcher
        self.port_id = port_id
        self.last_color_code = -1
        self.status_text = "BRAK_INFO"
        self.last_rgb =  {"r": 0, "g": 0, "b": 0}

    async def setup_sensor(self):
        """Konfiguruje port czujnika koloru w trybie RGB (Mode 5)."""
        if not self.train.client or not self.train.client.is_connected:
            return False
        print(f"[{self.train.name}] Czekam na uruchomienie portów w hubie ...")
        await asyncio.sleep(4)

        # Włączamy tryb RGB (Mode 5) z minimalną deltą (0x05), żeby nie zapchać Bluetooth
        payload = bytearray([0x0A, 0x00, 0x41, self.port_id, 0x05, 0x05, 0x00, 0x00, 0x00, 0x01])
        await self.train.client.write_gatt_char(LEGO_HUB_CHARACTERISTIC, payload)
        print(f"[{self.train.name}] Wysłano żądanie aktywacji czujnika (Tryb RGB). Port {self.port_id}")

    def decode_rgb_to_lego_color(self, data):
        """Zamienia surowe dane RGB z czujnika na legowski kod koloru."""
        # W trybie RGB ramka musi mieć co najmniej 10 bajtów
        if len(data) < 10:
            return 0
        
        # Wyciągamy wartości RGB (składamy z dwóch bajtów: Low i High)
        r = data[4] + (data[5] << 8)
        g = data[6] + (data[7] << 8)
        b = data[8] + (data[9] << 8)
        
        # TŁUMIK TŁA (Ignorowanie jasnej podłogi i ciemnych torów)
        if r < 100 and g < 100 and b < 100:
            return 0
        
        # OBLICZANIE DOMINUJĄCEGO KOLORU
        max_val = max(r, g, b)
        
        # BIAŁY (10) - wszystkie kanały jasne i o podobnej wartości
        if abs(r - g) < 50 and abs(g - b) < 50 and max_val > 150:
            return 10
            
        # ZIELONY (6) - Zielony dominuje nad czerwonym i niebieskim
        if g == max_val and g > r + 30 and g > b + 30:
            return 6
            
        # NIEBIESKI (3) - Niebieski dominuje nad resztą
        if b == max_val and b > r + 30 and b > g + 20:
            return 3
            
        # ŻÓŁTY (7) - Mieszanka czerwonego i zielonego, bardzo mało niebieskiego
        if abs(r - g) < 60 and r > 150 and g > 150 and b < r - 50:
            return 7
            
        # CZERWONY (9) - Czerwony wyraźnie dominuje
        if r == max_val and r > g + 50 and r > b + 50:
            return 9

        # Jeśli światło nie pasuje do żadnego z naszych klocków, uznajemy za "BRAK"
        return 0

    def process_notification(self, data):
        """Przetwarza przychodzące dane z Huba."""
        if len(data) >= 10 and data[2] == 0x45 and data[3] == self.port_id:
            
            # --- ZAPISYWANIE DANYCH DO PODGLĄDU NA ŻYWO ---
            r = data[4] + (data[5] << 8)
            g = data[6] + (data[7] << 8)
            b = data[8] + (data[9] << 8)
            self.last_rgb = {"r": r, "g": g, "b": b} 
            # ----------------------------------------------
            
            color_code = self.decode_rgb_to_lego_color(data)
            
            # Reagujemy tylko na faktyczną ZMIANĘ koloru
            if color_code != self.last_color_code:
                # Nie chcemy wywoływać akcji "BRAK_INFO", jeśli zmienił się po prostu odcień tła
                if color_code != 0 or self.last_color_code != -1: 
                    self.last_color_code = color_code
                    asyncio.create_task(self.handle_color(color_code))

    async def handle_color(self, code):
        """Główna logika wykonywania akcji (Stop, Zwolnij, Strefy)."""
        try:
            cfg = COLORS_CONFIG.get(code)
        
            if not cfg:
                return

            role = cfg.get("role")
            
            if role == "action" and cfg["action"] == "stop":
                duration = cfg.get("duration")
                prev_speed = self.train.speed
                self.status_text = f"STOP ({duration}s)"
                self.dispatcher.log(f"[STOP] {self.train.name}: Postój na {cfg['label']}.")
                await self.train.set_speed(0)
                
                if prev_speed != 0:
                    await asyncio.sleep(duration)
                    self.status_text = "ODJAZD"
                    await self.train.set_speed(prev_speed)

            elif role == "action" and cfg["action"] == "slow":
                duration = cfg.get("duration")
                speed_limit = cfg.get("speed_limit")

                self.status_text = f"LIMIT ({speed_limit}%)"
                prev_speed = self.train.speed

                if abs(self.train.speed) > speed_limit:
                    self.dispatcher.log(f"[LIMIT] {self.train.name}: Zwalniam ({cfg['label']}).")
                    await self.train.set_speed(speed_limit if self.train.speed > 0 else -speed_limit)
                    await asyncio.sleep(duration)
                    await self.train.set_speed(prev_speed) 
                    self.status_text = "LIMIT KONIEC"

            elif role == "zone":
                zone_id = cfg["zone_id"]
                self.status_text = f"STREFA {zone_id}"
                await self.dispatcher.request_entry(self.train, zone_id)

            elif role == "none":
                self.status_text = "JAZDA"
        
        except Exception as e:
            self.status_text = f"ERROR"
            self.dispatcher.log(f"[ERROR] Kolor {code} - {str(e)}")