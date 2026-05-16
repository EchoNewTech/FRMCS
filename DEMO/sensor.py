import asyncio
from config import COLORS_CONFIG
from train import LEGO_HUB_CHARACTERISTIC

class ColorDetector:
    def __init__(self, train, dispatcher, port_id=0x01):
        self.train = train
        self.dispatcher = dispatcher
        self.port_id = port_id
        self.last_color_code = None
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

    def decode_rgb_to_lego_color(self, r, g, b):
        """Zamienia przeskalowane dane RGB (0-255) na legowski kod koloru."""
        
        # Próg szumu (Tłumik tła) - odrzucamy bardzo ciemne odczyty
        if r < 20 and g < 20 and b < 20:
            return None

        # Automatyczne dopasowanie do konfiguracji
        for code, cfg in COLORS_CONFIG.items():
            if "rgb_range" not in cfg:
                continue
                
            ranges = cfg["rgb_range"]
            # Sprawdzamy czy R, G i B mieszczą się w zdefiniowanych widełkach
            match_r = ranges["r"][0] <= r <= ranges["r"][1]
            match_g = ranges["g"][0] <= g <= ranges["g"][1]
            match_b = ranges["b"][0] <= b <= ranges["b"][1]
            
            if match_r and match_g and match_b:
                return code

        return None

    def process_notification(self, data):
        if len(data) >= 10 and data[2] == 0x45 and data[3] == self.port_id:
            # Skalowanie danych RGB[cite: 6]
            r = min(255, int((data[4] + (data[5] << 8)) / 4))
            g = min(255, int((data[6] + (data[7] << 8)) / 4))
            b = min(255, int((data[8] + (data[9] << 8)) / 4))

            self.last_rgb = {"r": r, "g": g, "b": b} 
            color_code = self.decode_rgb_to_lego_color(r, g, b)
            
            # Reagujemy na zmianę (jeśli kolor jest inny niż poprzedni)[cite: 6]
            if color_code != self.last_color_code:
                self.last_color_code = color_code
                if color_code is not None:
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