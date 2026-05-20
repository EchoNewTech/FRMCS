import asyncio
from app.config import COLORS_CONFIG
from app.constants import LEGO_HUB_CHARACTERISTIC

class ColorDetector:
    def __init__(self, train, dispatcher, port_id=0x01):
        self.train = train
        self.dispatcher = dispatcher
        self.port_id = port_id
        self.last_color_code = None
        self.last_rgb =  {"r": 0, "g": 0, "b": 0}
        self.is_processing_stop = False
        self.is_processing_slow = False # NOWA FLAGA DLA ZWOLNIENIA

    async def setup_sensor(self):
        """Activates RGB Mode 5 on the color sensor."""
        if not self.train.client or not self.train.client.is_connected:
            return False

        payload = bytearray([0x0A, 0x00, 0x41, self.port_id, 0x05, 0x05, 0x00, 0x00, 0x00, 0x01])
        await self.train.client.write_gatt_char(LEGO_HUB_CHARACTERISTIC, payload)
        print(f"[{self.train.name}] Sensor Activated (Mode RGB). Port {self.port_id}")

    def decode_rgb_to_lego_color(self, r, g, b):
        if r < 20 and g < 20 and b < 20:
            return None

        priority = ["ST", "SL"]
        for code in priority:
            if code in COLORS_CONFIG and "rgb_range" in COLORS_CONFIG[code]:
                ranges = COLORS_CONFIG[code]["rgb_range"]
                if (ranges["r"][0] <= r <= ranges["r"][1] and 
                    ranges["g"][0] <= g <= ranges["g"][1] and 
                    ranges["b"][0] <= b <= ranges["b"][1]):
                    return code

        for code, cfg in COLORS_CONFIG.items():
            if code in priority or "rgb_range" not in cfg: continue
            ranges = cfg["rgb_range"]
            if (ranges["r"][0] <= r <= ranges["r"][1] and 
                ranges["g"][0] <= g <= ranges["g"][1] and 
                ranges["b"][0] <= b <= ranges["b"][1]):
                return code
        return None

    def process_notification(self, data):
        if len(data) >= 6 and data[2] == 0x04 and data[5] == 0x3d:
            detected_port = data[3]
            print(f"[!] HARDWARE DETECTED: Port {detected_port} for {self.train.name}")
            self.port_id = detected_port
            asyncio.create_task(self.setup_sensor())
            return

        if len(data) >= 10 and data[2] == 0x45 and data[3] == self.port_id:
            r = min(255, int((data[4] + (data[5] << 8)) / 4))
            g = min(255, int((data[6] + (data[7] << 8)) / 4))
            b = min(255, int((data[8] + (data[9] << 8)) / 4))

            self.last_rgb = {"r": r, "g": g, "b": b} 
            color_code = self.decode_rgb_to_lego_color(r, g, b)
            
            if color_code != self.last_color_code:
                self.last_color_code = color_code
                if color_code is not None:
                    asyncio.create_task(self.handle_color(color_code))
                    
    async def handle_color(self, code):
        try:
            cfg = COLORS_CONFIG.get(code)
            if not cfg: return

            role = cfg.get("role")
            
            if role == "action":
                if cfg["action"] == "stop":
                    if self.is_processing_stop: return
                    self.is_processing_stop = True
                    
                    try:
                        duration = cfg.get("duration")
                        captured_speed = self.train.speed
                        
                        self.dispatcher.log(f"[STOP] {self.train.name}: Stopped at {cfg['label']}.")
                        
                        await self.train.send_speed(0)
                        await asyncio.sleep(duration)
                        
                        if self.train not in self.dispatcher.waiting_trains:
                            await self.train.send_speed(captured_speed)
                    finally:
                        self.is_processing_stop = False

                elif cfg["action"] == "slow":
                    # BLOKADA: Jeśli już zwalnia, ignoruj kolejne sygnały brązowe
                    if self.is_processing_slow: return
                    self.is_processing_slow = True
                    
                    try:
                        duration = cfg.get("duration")
                        speed_limit = cfg.get("speed_limit")
                        captured_speed = self.train.speed

                        if abs(captured_speed) > speed_limit:
                            self.dispatcher.log(f"[LIMIT] {self.train.name}: Slowing down ({cfg['label']}).")
                            
                            new_speed = speed_limit if captured_speed > 0 else -speed_limit
                            await self.train.send_speed(new_speed)
                            
                            await asyncio.sleep(duration)
                            
                            # KLUCZOWE: Przywróć poprzednią prędkość TYLKO, jeśli pociąg nie stanął na czerwonym,
                            # nie został zablokowany przez dyspozytora i... UŻYTKOWNIK NIE ZMIENIŁ PRĘDKOŚCI RĘCZNIE!
                            if not self.is_processing_stop and self.train not in self.dispatcher.waiting_trains:
                                if self.train.speed == new_speed:
                                    await self.train.send_speed(captured_speed) 
                    finally:
                        self.is_processing_slow = False

            elif role == "zone":
                zone_id = cfg["zone_id"]
                label = cfg.get("label", f"ZONE {zone_id}")
                
                self.train.section = f"ZONE {zone_id} ({label})"
                await self.dispatcher.request_entry(self.train, zone_id)
        
        except Exception as e:
            self.dispatcher.log(f"[ERROR] Color {code} - {str(e)}")
