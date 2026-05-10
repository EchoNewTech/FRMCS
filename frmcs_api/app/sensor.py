import asyncio
from app.config import COLORS_CONFIG
from app.constants import LEGO_HUB_CHARACTERISTIC

class ColorDetector:
    def __init__(self, train, dispatcher=None, port_id=0x01):
        self.train = train
        self.dispatcher = dispatcher
        self.port_id = port_id
        self.last_color_code = None
        self.status_text = "DRIVING"
        self.is_processing = False

    async def setup_sensor(self):
        if not self.train.client or not self.train.client.is_connected:
            return False
        # Aktywacja sensora
        payload = bytearray([0x0A, 0x00, 0x41, self.port_id, 0x05, 0x05, 0x00, 0x00, 0x00, 0x01])
        await self.train.client.write_gatt_char(LEGO_HUB_CHARACTERISTIC, payload)

    def decode_rgb(self, r, g, b):
        # Najpierw AKCJE (Stop, Slow)
        priority = ["ST", "SL"]
        for code in priority:
            if code in COLORS_CONFIG:
                cfg = COLORS_CONFIG[code]
                rng = cfg["rgb_range"]
                if (rng["r"][0] <= r <= rng["r"][1] and 
                    rng["g"][0] <= g <= rng["g"][1] and 
                    rng["b"][0] <= b <= rng["b"][1]):
                    return code
        
        # Potem STREFY
        for code, cfg in COLORS_CONFIG.items():
            if code in priority: continue
            if "rgb_range" in cfg:
                rng = cfg["rgb_range"]
                if (rng["r"][0] <= r <= rng["r"][1] and 
                    rng["g"][0] <= g <= rng["g"][1] and 
                    rng["b"][0] <= b <= rng["b"][1]):
                    return code
        return None

    def process_notification(self, data):
        # Sprawdzamy port i typ danych (0x45)
        if len(data) >= 10 and data[2] == 0x45 and data[3] == self.port_id:
            r = data[4] + (data[5] << 8)
            g = data[6] + (data[7] << 8)
            b = data[8] + (data[9] << 8)
            
            # Zawsze aktualizuj RGB, żeby na wykresach było widać ruch
            self.train.rgb = {"r": r, "g": g, "b": b}

            color_code = self.decode_rgb(r, g, b)
            
            # Jeśli kolor się zmienił (np. wjechał na niebieski lub zjechał z niego na tory)
            if color_code != self.last_color_code:
                self.last_color_code = color_code
                
                if color_code:
                    # Wykryto konkretną strefę lub akcję
                    asyncio.create_task(self.handle_color(color_code))
                else:
                    # Brak koloru (tory) - wracamy do DRIVING tylko jeśli nie trwa akcja STOP
                    if not self.is_processing:
                        self.status_text = "DRIVING"
                        self.train.section = "DRIVING"

    async def handle_color(self, code):
        if self.is_processing: return
        cfg = COLORS_CONFIG.get(code)
        if not cfg: return
        
        role = cfg.get("role")
        
        if role == "action":
            self.is_processing = True
            try:
                prev_speed = self.train.speed
                action = cfg.get("action")
                
                if action == "stop":
                    self.status_text = f"STOP ({cfg['duration']}s)"
                    self.train.section = self.status_text
                    await self.train.stop()
                    await asyncio.sleep(cfg['duration'])
                    await self.train.send_speed(prev_speed)
                
                elif action == "slow":
                    limit = cfg['speed_limit']
                    self.status_text = f"SLOW ({limit}%)"
                    self.train.section = self.status_text
                    await self.train.send_speed(limit if prev_speed > 0 else -limit)
                    await asyncio.sleep(cfg['duration'])
                    await self.train.send_speed(prev_speed)
                
                self.status_text = "DRIVING"
                self.train.section = "DRIVING"
            finally:
                self.is_processing = False
        
        elif role == "zone" and self.dispatcher:
            # Strefy nie blokują sensora flagą is_processing
            self.status_text = f"ZONE {cfg['zone_id']}"
            self.train.section = self.status_text
            await self.dispatcher.request_entry(self.train, cfg["zone_id"])
