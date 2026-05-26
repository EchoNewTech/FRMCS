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

# Import biblioteki dla ekranu OLED
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
LUMA_AVAILABLE = True

# Import radaru Bluetooth
from bleak import BleakScanner

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

SPEAKER_PIN = 18

# ========================================================
# CONTROLLER SPRZĘTOWY: GŁOŚNIK I WYŚWIETLACZ GROVE
# ========================================================
class HardwareStationHUD:
    def __init__(self):
        self.device = None
        self.pwm = None
        
        if LUMA_AVAILABLE:
            try:
                serial = i2c(port=1, address=0x3C)
                self.device = ssd1306(serial)
                
                image = Image.new("1", (self.device.width, self.device.height))
                draw = ImageDraw.Draw(image)
                font = ImageFont.load_default()
                draw.text((20, 20), "SYSTEM FRMCS", font=font, fill="white")
                draw.text((20, 35), "URUCHAMIANIE...", font=font, fill="white")
                self.device.display(image.convert(self.device.mode))
                print("[HARDWARE] Wyświetlacz Grove OLED zainicjalizowany (LUMA).")
            except Exception as e:
                print(f"[HARDWARE] Brak ekranu OLED lub błąd I2C: {e}")                
        
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
        if not self.pwm: 
            return

        def _play():
            try:
                VOLUME = 10 
                self.pwm.ChangeFrequency(392.00)
                self.pwm.ChangeDutyCycle(VOLUME) 
                time.sleep(0.6)
                self.pwm.ChangeFrequency(523.25)
                time.sleep(0.6)
                self.pwm.ChangeFrequency(659.25)
                time.sleep(1.2)
                self.pwm.ChangeDutyCycle(0)
            except Exception as e:
                print(f"[AUDIO BŁĄD] {e}")
            
        threading.Thread(target=_play, daemon=True).start()

    def update_display(self, zones_data):
        if not self.device: return
        
        image = Image.new("1", (self.device.width, self.device.height))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        
        draw.text((2, 0), "STACJA GLOWNA", font=font, fill="white")
        draw.line((0, 12, 128, 12), fill="white")
        
        y_offset = 16
        for z_id, occupant in zones_data.items():
            status_text = f"STREFA {z_id}: "
            status_text += occupant if occupant else "WOLNA"
            
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
# GLOBALNY SKANER BLE (RADAR)
# ========================================================
_global_scanner = None

async def _hub_discovery_callback(device, advertisement_data):
    """Wywoływane w tle, gdy skaner 'usłyszy' urządzenie BLE."""
    target_train = None
    for t in trains.values():
        if t.mac.upper() == device.address.upper():
            target_train = t
            break
            
    if not target_train:
        return 

    if getattr(target_train, 'client', None) and target_train.client.is_connected:
        return
        
    if getattr(target_train, 'is_connecting', False):
        return

    print(f"[SKANER] Wykryto aktywny Hub: {target_train.name}! Uruchamiam łączenie.")
    asyncio.create_task(_connect_task_wrapper(target_train, device))

async def _connect_task_wrapper(train, device):
    """Izolowane zadanie dla szybkiego zestawienia połączenia."""
    success = await train.connect_to_device(device)
    if success:
        train.detector = ColorDetector(train, dispatcher)
        await train.detector.setup_sensor()
        logger.log(f"[{train.name}] Auto-Połączenie (BT) ustanowione.")

async def start_global_scanner():
    global _global_scanner
    if _global_scanner:
        return
        
    print("[SKANER] Uruchamianie radaru BLE...")
    try:
        _global_scanner = BleakScanner(detection_callback=_hub_discovery_callback)
        await _global_scanner.start()
    except Exception as e:
        print(f"[SKANER BŁĄD] {e}")

async def stop_global_scanner():
    global _global_scanner
    if _global_scanner:
        try:
            await _global_scanner.stop()
        except:
            pass
        _global_scanner = None
        print("[SKANER] Radar BLE wyłączony.")

# ========================================================
# FASTAPI
# ========================================================
@asynccontextmanager
async def lifespan(_: FastAPI):
    if hw_hud.device:
        hw_hud.update_display({1: None, 2: None, 3: None, 4: None})
    yield
    # Sprzątanie przy wyłączaniu serwera
    await stop_global_scanner()
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
    global _global_scanner
    if not _global_scanner:
        await start_global_scanner()
        
    logger.log(f"[{t.name}] Oczekiwanie na sygnał. Naciśnij zielony przycisk na hubie!")
    return {"status": "scanning_started"}
    
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

    if getattr(t, 'client', None) and t.client.is_connected:
        await t.set_speed(0)
        await t.client.disconnect()
        t.detector = None
        logger.log(f"[{t.name}] Rozłączono pociąg (Bluetooth).")

    return {"status": "disconnected"}

@app.post("/api/move/{tid}/{direction}")
async def api_move(tid: str, direction: str):
    t = trains.get(tid)
    if not getattr(t, 'client', None) or not t.client.is_connected:
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
    if not getattr(t, 'client', None) or not t.client.is_connected:
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
    
    if current_zones != _last_known_zones:
        hw_hud.update_display(current_zones)
        for z_id, occupant in current_zones.items():
            if occupant and _last_known_zones.get(z_id) != occupant:
                hw_hud.play_ding_dong() 
                break
        _last_known_zones = current_zones.copy()

    data = {
        "logs": logger.logs,
        "trains": {},
        "zones": current_zones
    }
    
    for tid, t in trains.items():
        conn_type = None
        if getattr(t, 'client', None) and t.client.is_connected:
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