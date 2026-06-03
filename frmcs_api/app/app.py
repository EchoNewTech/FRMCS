from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
import asyncio
import traceback
import os
import threading
import time
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path

from app.lego_train import LegoTrain
from app.dispatcher import ZoneDispatcher, SystemLogger
from app.config import TRAINS_CONFIG

from PIL import Image, ImageDraw, ImageFont

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
LUMA_AVAILABLE = True

import RPi.GPIO as GPIO
import urllib.request



SPEAKER_PIN = 18

# --- CONFIG & ENV ---
load_dotenv(Path(__file__).resolve().parent / ".env.local")

logger = SystemLogger(max_logs=10)
dispatcher = ZoneDispatcher(logger)

# Inicjalizacja pociągów
trains = {
    "express": LegoTrain("Express", os.getenv("EXPRESS_MAC", ""), "express"),
    "cargo": LegoTrain("Cargo", os.getenv("CARGO_MAC", ""), "cargo")
}

# Przypisujemy telemetrie bez użycia os.getenv - bezpośrednio z konfiguracji
trains["express"].telemetry_url = TRAINS_CONFIG.get("express", {}).get("rasp_url", "")
trains["cargo"].telemetry_url = TRAINS_CONFIG.get("cargo", {}).get("rasp_url", "")

class SpeedRequest(BaseModel):
    speed: int

class CollisionLogRequest(BaseModel):
    g_value: float

class HardwareStationHUD:
    def __init__(self):
        self.oled = None
        self.pwm = None
        
        if LUMA_AVAILABLE:
            try:
                serial = i2c(port=1, address=0x3C)
                self.device = ssd1306(serial)
                
                image = Image.new("1", (self.device.width, self.device.height))
                draw = ImageDraw.Draw(image)
                font = ImageFont.load_default()
                draw.text((20, 20), "SYSTEM FRMCS", font=font, fill="white")
                draw.text((20, 35), "RUNNING...", font=font, fill="white")
                self.device.display(image.convert(self.device.mode))
                print("[HARDWARE] Grove OLED display initialized (LUMA).")
            except Exception as e:
                print(f"[HARDWARE] No OLED display or I2C error: {e}")

        # 2. Inicjalizacja Głośnika Grove (PWM przez RPi.GPIO)
        if GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(SPEAKER_PIN, GPIO.OUT)
                self.pwm = GPIO.PWM(SPEAKER_PIN, 440)
                self.pwm.start(0)  
                print("[HARDWARE] Grove speaker (PWM) initialized.")
            except Exception as e:
                print(f"[HARDWARE] Inicjalization error of speaker PWM: {e}")

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
                print(f"[AUDIO ERROR] {e}")
            
        threading.Thread(target=_play, daemon=True).start()

    def update_display(self, zones_data):
        if not self.device: return
        
        image = Image.new("1", (self.device.width, self.device.height))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        
        draw.text((2, 0), "MAIN STATION", font=font, fill="white")
        draw.line((0, 12, 128, 12), fill="white")
        
        y_offset = 16
        for z_id, occupant in zones_data.items():
            status_text = f"ZONE {z_id}: "
            status_text += occupant if occupant else "FREE"
            
            if occupant:
                draw.rectangle((0, y_offset, 128, y_offset + 10), fill="white")
                draw.text((2, y_offset), status_text, font=font, fill="black")
            else:
                draw.text((2, y_offset), status_text, font=font, fill="white")
                
            y_offset += 12
            if y_offset > 54: break 
            
        self.device.display(image.convert(self.device.mode))

hw_hud = HardwareStationHUD()

class AlarmManager:
    def __init__(self):
        self.is_collision_active = False

alarm_manager = AlarmManager()

async def display_updater():
    global _last_known_zones

    _last_known_zones = {}

    while True:
        try:
            current_zones = {
                z_id: dispatcher.zones[z_id].name if dispatcher.zones.get(z_id) else None
                for z_id in dispatcher.zones
            }
            hw_hud.update_display(current_zones)

            # Logika dźwięku: jeśli ktoś wjechał do strefy, a wcześniej go tam nie było
            for z_id, occupant in current_zones.items():
                if occupant and _last_known_zones.get(z_id) != occupant:
                    hw_hud.play_ding_dong()
                    break
            
            _last_known_zones = current_zones.copy()

        except Exception as e:
            print(f"[OLED/AUDIO ERROR] {e}")
        await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(display_updater())
    yield
    task.cancel()
    for train in trains.values():
        if train.is_connected: await train.disconnect()
    if GPIO and hw_hud.pwm:
        hw_hud.pwm.stop()
        GPIO.cleanup()

app = FastAPI(lifespan=lifespan, docs_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- ENDPOINTY ---
@app.get("/docs", include_in_schema=False)
async def custom_docs():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="API Docs",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
        swagger_ui_parameters={"presets": ["SwaggerUIBundle.presets.apis", "SwaggerUIStandalonePreset"]}
    )

@app.post("/{train_id}/connect")
async def connect_to_train(train_id: str):
    if train_id not in trains: return {"status": "error", "message": "Not found"}
    try:
        await trains[train_id].connect(dispatcher=dispatcher)
        return {"status": "success"}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

@app.post("/{train_id}/disconnect")
async def disconnect_train(train_id: str):
    if train_id not in trains: return {"status": "error", "message": "Not found"}
    try:
        await trains[train_id].disconnect()
        for z_id, occupant in list(dispatcher.zones.items()):
            if occupant == trains[train_id].name:
                await dispatcher.free_zone_and_resume(z_id)
                
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/{train_id}/position")
async def get_train_position(train_id: str):
    if train_id not in trains: return {"status": "error", "message": "Not found"}
    train = trains[train_id]

    return {
        "status": "success",
        "data": {
            "id": train_id,
            "name": train.name,
            "type": train.train_type,
            "connected": train.is_connected,
            "speed": train.speed,
            "section": getattr(train, "section", "DISCONNECTED"),
            "rgb": train.rgb,
            "telemetry_url": train.telemetry_url
        }
    }

@app.get("/config")
async def get_api_config():
    from app.config import COLORS_CONFIG # Dynamiczny import zapobiegający problemom przy resecie
    return {
        "trains": {
            "express": {"name": "Express"},
            "cargo": {"name": "Cargo"}
        },
        "colors": {
            "S1": {"zone_id": 1, "label": "BLUE"},
            "S2": {"zone_id": 2, "label": "GREEN"},
            "S3": {"zone_id": 3, "label": "ORANGE"},
            "S4": {"zone_id": 4, "label": "WHITE"}
        }
    }

@app.get("/status")
async def get_system_status():
    return {
        "logs": logger.logs,
        "trains": {
            tid: {
                "connected": t.is_connected,
                "speed": t.speed,
                "section": getattr(t, "section", "DISCONNECTED"),
                "telemetry_url": t.telemetry_url
            } for tid, t in trains.items()
        },
        "zones": {
            z_id: (occ.name if hasattr(occ, 'name') else occ) if occ else None 
            for z_id, occ in dispatcher.zones.items()
        },
    }

@app.post("/{train_id}/telemetry/reset")
async def reset_telemetry(train_id: str):
    if train_id not in trains:
        return {"status": "error", "message": "Not found"}
    
    t = trains[train_id]
    
    # 1. Przekazanie żądania POST fizycznie do malinki w pociągu
    if getattr(t, 'telemetry_url', ""):
        def _send_reset_to_train():
            try:
                url = f"{t.telemetry_url}/api/telemetry/reset"
                req = urllib.request.Request(url, method='POST')
                urllib.request.urlopen(req, timeout=3)
            except Exception as e:
                print(f"[{t.name}] Error during restarting Raspberry: {e}")
        
        # Odpalamy w tle, żeby nie "zawiesić" dyspozytora na czas wysyłania zapytania
        await asyncio.to_thread(_send_reset_to_train)
        logger.log(f"[{t.name}] Sensors reseted (INS) physically in train.")

    # 2. Odblokowanie alarmu na głównym serwerze
    alarm_manager.is_collision_active = False 
    
    return {"status": "success"}


@app.post("/{train_id}/collision")
async def log_collision_event(train_id: str, req: CollisionLogRequest):
    if train_id in trains:
        t = trains[train_id]
        logger.log(f"CRITICAL ALARM: Collision at {t.name.upper()} ({req.g_value} m/s²)")
    return {"status": "success"}


@app.post("/{train_id}/speed")
async def update_speed(train_id: str, req: SpeedRequest):
    if train_id not in trains: return {"status": "error", "message": "Not found"}
    train = trains[train_id]
    
    if train in dispatcher.waiting_trains:
        return {"status": "error", "message": "Blocked by dispatcher"}
        
    await train.send_speed(req.speed)
    return {"status": "success"}

@app.post("/{train_id}/stop")
async def stop_train(train_id: str):
    if train_id not in trains: return {"status": "error", "message": "Not found"}
    await trains[train_id].stop()
    
    return {"status": "success"}
