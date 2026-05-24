import asyncio
import time
import threading
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
from PIL import Image, ImageDraw, ImageFont

# Import biblioteki dla głośnika (PWM)
import RPi.GPIO as GPIO

# Import NOWEJ, stabilnej biblioteki dla ekranu OLED
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
LUMA_AVAILABLE = True

from train import LegoTrain
from sensor import ColorDetector
from dispatcher import SystemLogger, ZoneDispatcher
from config import LOCAL_IP, TRAINS_CONFIG, COLORS_CONFIG

BASE_DIR = Path(__file__).parent

logger = SystemLogger(max_logs=8)
dispatcher = ZoneDispatcher(logger)

# Automatyczne dodawanie pociągów z konfiguracji
trains = {
    tid: LegoTrain(tinfo["name"], tinfo["mac"]) for tid, tinfo in TRAINS_CONFIG.items()
}

# CONFIG: Pin GPIO (BCM 18 to fizyczny Pin 12 na płycie)
SPEAKER_PIN = 18

# ========================================================
# CONTROLLER SPRZĘTOWY: GŁOŚNIK I WYŚWIETLACZ GROVE
# ========================================================
class HardwareStationHUD:
    def __init__(self):
        self.device = None
        self.pwm = None
        
        # 1. Inicjalizacja Ekranu OLED (Luma.oled) - odporna na konflikty
        if LUMA_AVAILABLE:
            try:
                serial = i2c(port=1, address=0x3C)
                self.device = ssd1306(serial)
                
                # --- EKRAN STARTOWY ---
                image = Image.new("1", (self.device.width, self.device.height))
                draw = ImageDraw.Draw(image)
                font = ImageFont.load_default()
                draw.text((20, 20), "SYSTEM FRMCS", font=font, fill="white")
                draw.text((20, 35), "URUCHAMIANIE...", font=font, fill="white")
                self.device.display(image.convert(self.device.mode))
                print("[HARDWARE] Wyświetlacz Grove OLED zainicjalizowany (LUMA).")
            except Exception as e:
                print(f"[HARDWARE] Brak ekranu OLED lub błąd I2C: {e}")                
        
        # 2. Inicjalizacja Głośnika Grove (PWM przez RPi.GPIO)
        if GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(SPEAKER_PIN, GPIO.OUT)
                self.pwm = GPIO.PWM(SPEAKER_PIN, 440)
                self.pwm.start(0)
                print("[HARDWARE] Sprzętowy głośnik Grove (PWM) zainicjalizowany.")
            except Exception as e:
                print(f"[HARDWARE] Błąd inicjalizacji głośnika PWM: {e}")

    def play_ding_dong(self):
        """Generuje 3 sprzętowe tony charakterystyczne dla polskich dworców."""
        if not self.pwm: 
            return

        def _play():
            try:
                # Głośność ustawiona na 10, aby dźwięk był czysty i nie przesterowany
                VOLUME = 10 
                
                # Ton 1: G4 (392.00 Hz)
                self.pwm.ChangeFrequency(392.00)
                self.pwm.ChangeDutyCycle(VOLUME) 
                time.sleep(0.6)
                
                # Ton 2: C5 (523.25 Hz)
                self.pwm.ChangeFrequency(523.25)
                time.sleep(0.6)
                
                # Ton 3: E5 (659.25 Hz)
                self.pwm.ChangeFrequency(659.25)
                time.sleep(1.2)
                
                # Cisza
                self.pwm.ChangeDutyCycle(0)
            except Exception as e:
                print(f"[AUDIO BŁĄD] {e}")
            
        threading.Thread(target=_play, daemon=True).start()

    def update_display(self, zones_data):
        """Rysuje aktualny rozkład i zajętość stref na ekranie OLED."""
        if not self.device: return
        
        image = Image.new("1", (self.device.width, self.device.height))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        
        # Nagłówek stacji
        draw.text((2, 0), "STACJA GLOWNA", font=font, fill="white")
        draw.line((0, 12, 128, 12), fill="white")
        
        # Wyświetlanie stanu stref
        y_offset = 16
        for z_id, occupant in zones_data.items():
            status_text = f"STREFA {z_id}: "
            status_text += occupant if occupant else "WOLNA"
            
            # Negatyw dla zajętych stref (wyróżnienie wizualne)
            if occupant:
                draw.rectangle((0, y_offset, 128, y_offset + 10), fill="white")
                draw.text((2, y_offset), status_text, font=font, fill="black")
            else:
                draw.text((2, y_offset), status_text, font=font, fill="white")
                
            y_offset += 12
            if y_offset > 54: break 
            
        self.device.display(image.convert(self.device.mode))

hw_hud = HardwareStationHUD()
# ========================================================

@asynccontextmanager
async def lifespan(_: FastAPI):
    if hw_hud.device:
        hw_hud.update_display({1: None, 2: None, 3: None, 4: None})
    yield
    for t in trains.values():
        if getattr(t, 'client', None) and t.client.is_connected:
            await t.set_speed(0)
            await t.client.disconnect()
    if GPIO:
        if hw_hud.pwm:
            hw_hud.pwm.stop()
        GPIO.cleanup()

app = FastAPI(lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def index():
    path = BASE_DIR / "index.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Plik index.html nie istnieje")
    return path.read_text(encoding="utf-8")

@app.get("/stacja", response_class=HTMLResponse)
async def stacja():
    path = BASE_DIR / "station.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Plik station.html nie istnieje")
    return path.read_text(encoding="utf-8")

@app.get("/api/config")
async def api_config():
    return {"trains": TRAINS_CONFIG, "colors": COLORS_CONFIG}

@app.post("/api/connect/{tid}")
async def api_connect(tid: str):
    if tid not in trains:
        raise HTTPException(status_code=404, detail="Nie znaleziono pociągu")
    
    t = trains[tid]
    status_conn = await t.connect()
    
    if status_conn:
        t.is_virtual = False
        t.detector = ColorDetector(t, dispatcher)
        await t.detector.setup_sensor()
        logger.log(f"[{t.name}] Połączono (BT) i aktywowano skaner.")
        return {"status": "success"}
    else:
        logger.log(f"[{t.name}] Brak sprzętu. Aktywacja trybu WIRTUALNEGO.")        
        
        async def virtual_set_speed(target_speed):
            t.speed = max(-100, min(100, target_speed))
            return True
            
        async def virtual_stop():
            t.speed = 0
            return True
            
        t.set_speed = virtual_set_speed
        t.stop = virtual_stop
        t.is_virtual = True 
        t.detector = ColorDetector(t, dispatcher)
        return {"status": "virtual"}

@app.post("/api/disconnect/{tid}")
async def api_disconnect(tid: str):
    t = trains.get(tid)
    if not t:
        raise HTTPException(status_code=404, detail="Nie znaleziono pociągu")

    for z_id in list(dispatcher.zones.keys()):
        if dispatcher.zones[z_id] == t:
            dispatcher.zones[z_id] = None
            logger.log(f"[{t.name}] Usunięto z makiety (STREFA {z_id} wolna).")
            
    if t in dispatcher.waiting_trains:
        del dispatcher.waiting_trains[t]

    if getattr(t, 'is_virtual', False):
        t.is_virtual = False
        t.speed = 0
        t.detector = None
        logger.log(f"[{t.name}] Zakończono symulację (DEV).")
        return {"status": "disconnected"}

    if getattr(t, 'client', None) and t.client.is_connected:
        await t.set_speed(0)
        await t.client.disconnect()
        t.detector = None
        logger.log(f"[{t.name}] Rozłączono pociąg (Bluetooth).")
        return {"status": "disconnected"}

    return {"status": "disconnected"}

@app.post("/api/move/{tid}/{direction}")
async def api_move(tid: str, direction: str):
    t = trains.get(tid)
    if not getattr(t, 'is_virtual', False) and (not getattr(t, 'client', None) or not t.client.is_connected):
        raise HTTPException(status_code=412, detail="Pociąg nie połączony")

    if t in dispatcher.waiting_trains:
        logger.log(f"[{t.name}] Zablokowano start! Pociąg czeka na zwolnienie strefy.")
        return {"speed": t.speed, "status": "blocked"}

    new_speed = t.speed + (10 if direction == "up" else -10)
    await t.set_speed(new_speed)
    return {"speed": t.speed}

@app.post("/api/stop/{tid}")
async def api_stop(tid: str):
    t = trains.get(tid)
    if not getattr(t, 'is_virtual', False) and (not getattr(t, 'client', None) or not t.client.is_connected):
        raise HTTPException(status_code=412, detail="Pociąg nie połączony")

    await t.set_speed(0)
    return {"status": "stopped", "speed": 0}

@app.post("/api/simulate/{tid}/{color_code}")
async def api_simulate_color(tid: str, color_code: str):
    t = trains.get(tid)
    if t and getattr(t, 'detector', None):
        await t.detector.handle_color(color_code)
        return {"status": "simulated"}
    raise HTTPException(status_code=400, detail="Brak detektora")

_last_known_zones = {}

@app.get("/api/status")
async def api_status():
    global _last_known_zones
    
    current_zones = {
        z_id: dispatcher.zones[z_id].name if dispatcher.zones.get(z_id) else None
        for z_id in dispatcher.zones
    }
    
    # --- INTERWENCJA HARDWARE ---
    if current_zones != _last_known_zones:
        hw_hud.update_display(current_zones)
        
        # Sprawdzamy, czy w jakiejś strefie pojawił się nowy pociąg (którego wcześniej tam nie było)
        for z_id, occupant in current_zones.items():
            if occupant and _last_known_zones.get(z_id) != occupant:
                hw_hud.play_ding_dong()  # Odpalenie fizycznego gongu PWM
                break
                
        _last_known_zones = current_zones.copy()
    # -----------------------------

    data = {
        "logs": logger.logs,
        "trains": {},
        "zones": current_zones
    }
    
    for tid, t in trains.items():
        conn_type = None
        if getattr(t, 'is_virtual', False):
            conn_type = "virtual"
        elif getattr(t, 'client', None) and t.client.is_connected:
            conn_type = "bt"

        code = getattr(t.detector, 'last_color_code', -1) if getattr(t, 'detector', None) else -1
        ui_color = COLORS_CONFIG.get(code, {}).get("ui_color", "gray")
        rgb_data = getattr(t.detector, 'last_rgb', {"r": 0, "g": 0, "b": 0}) if getattr(t, 'detector', None) else {"r": 0, "g": 0, "b": 0}

        data["trains"][tid] = {
            "speed": t.speed,
            "color_text": t.detector.status_text if getattr(t, 'detector', None) else "CZEKAM",
            "ui_color": ui_color,
            "connection": conn_type,
            "rgb": rgb_data
        }
    return data

if __name__ == "__main__":
    print("\n" + "="*55)
    print(" SYSTEM FRMCS JEST GOTOWY!")
    print(f" Otwórz panel sterowania: http://{LOCAL_IP}:8000")
    print(f" Otwórz tablicę stacyjną: http://{LOCAL_IP}:8000/stacja")
    print("="*55 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)