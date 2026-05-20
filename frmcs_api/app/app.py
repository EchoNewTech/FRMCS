from fastapi import FastAPI
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

try:
    import board
    import busio
except ImportError:
    board = None
    busio = None

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None

try:
    import adafruit_ssd1306
except ImportError:
    adafruit_ssd1306 = None


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

trains["express"].telemetry_url = os.getenv("EXPRESS_URL", "")
trains["cargo"].telemetry_url = os.getenv("CARGO_URL", "")

class SpeedRequest(BaseModel):
    speed: int



class HardwareStationHUD:
    def __init__(self):
        self.oled = None
        self.pwm = None
        
        if adafruit_ssd1306 and board and busio:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                # Używamy standardowego adresu 0x3C. Jeśli i2cdetect pokazał 3d, zmień parametr poniżej.
                self.oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
                
                # --- EKRAN STARTOWY ---
                image = Image.new("1", (self.oled.width, self.oled.height))
                draw = ImageDraw.Draw(image)
                font = ImageFont.load_default()
                draw.text((20, 20), "SYSTEM FRMCS", font=font, fill=255)
                draw.text((20, 35), "URUCHAMIANIE...", font=font, fill=255)
                self.oled.image(image)
                self.oled.show()
                print("[HARDWARE] Wyświetlacz Grove OLED zainicjalizowany (Adres 0x3C).")
            except Exception as e:
                print(f"[HARDWARE] Brak ekranu OLED lub błąd I2C: {e}")                
        # 2. Inicjalizacja Głośnika Grove (PWM przez RPi.GPIO)
        if GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(SPEAKER_PIN, GPIO.OUT)
                # Inicjalizacja PWM z częstotliwością startową 440Hz
                self.pwm = GPIO.PWM(SPEAKER_PIN, 440)
                self.pwm.start(0)  # 0% wypełnienia (Duty Cycle) oznacza całkowitą ciszę
                print("[HARDWARE] Sprzętowy głośnik Grove (PWM) zainicjalizowany.")
            except Exception as e:
                print(f"[HARDWARE] Błąd inicjalizacji głośnika PWM: {e}")

    def play_ding_dong(self):
        """Generuje 3 sprzętowe tony (G4, C5, E5) charakterystyczne dla polskich dworców."""
        if not self.pwm: 
            return

        def _play():
            try:
                # Ton 1: G4 (392.00 Hz)
                self.pwm.ChangeFrequency(392.00)
                self.pwm.ChangeDutyCycle(50)  # Uruchomienie fali prostokątnej (50% głośności)
                time.sleep(0.6)
                
                # Ton 2: C5 (523.25 Hz)
                self.pwm.ChangeFrequency(523.25)
                time.sleep(0.6)
                
                # Ton 3: E5 (659.25 Hz)
                self.pwm.ChangeFrequency(659.25)
                time.sleep(1.2)
                
                # Koniec sekwencji - powrót do ciszy
                self.pwm.ChangeDutyCycle(0)
            except Exception as e:
                print(f"[AUDIO BŁĄD] Wystąpił problem podczas generowania tonów PWM: {e}")
            
        # Odpalamy dźwięk w tle (w osobnym wątku), żeby nie zablokować głównego serwera FastAPI i pętli asyncio!
        threading.Thread(target=_play, daemon=True).start()

    def update_display(self, zones_data):
        """Rysuje aktualny rozkład i zajętość stref na ekranie OLED."""
        if not self.oled: return
        
        # Tworzenie czystego obrazu binarnego w pamięci podręcznej RAM
        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        
        # Nagłówek stacji
        draw.text((2, 0), "STACJA GŁÓWNA", font=font, fill=255)
        draw.line((0, 12, 128, 12), fill=255)
        
        # Wyświetlanie stanu stref
        y_offset = 16
        for z_id, occupant in zones_data.items():
            status_text = f"STREFA {z_id}: "
            status_text += occupant if occupant else "WOLNA"
            
            # Negatyw dla zajętych stref (wyróżnienie wizualne)
            if occupant:
                draw.rectangle((0, y_offset, 128, y_offset + 10), fill=255)
                draw.text((2, y_offset), status_text, font=font, fill=0)
            else:
                draw.text((2, y_offset), status_text, font=font, fill=255)
                
            y_offset += 12
            if y_offset > 54: break 
            
        self.oled.image(image)
        self.oled.show()


hw_hud = HardwareStationHUD()

async def display_updater():
    while True:
        try:
            current_zones = {
                z_id: dispatcher.zones[z_id].name if dispatcher.zones.get(z_id) else None
                for z_id in dispatcher.zones
            }
            hw_hud.update_display(current_zones)
        except Exception as e:
            print(f"[OLED ERROR] {e}")
        await asyncio.sleep(1) # Odświeżanie raz na sekundę


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

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- ENDPOINTY ---

@app.post("/{train_id}/connect")
async def connect_to_train(train_id: str):
    if train_id not in trains: return {"status": "error", "message": "Not found"}
    try:
        await trains[train_id].connect(dispatcher=dispatcher)
        return {"status": "success"}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

# --- BRAKUJĄCY ENDPOINT DISCONNECT ---
@app.post("/{train_id}/disconnect")
async def disconnect_train(train_id: str):
    if train_id not in trains: return {"status": "error", "message": "Not found"}
    try:
        await trains[train_id].disconnect()
        # Ważne: zwalniamy strefy, które zajmował pociąg po rozłączeniu
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

    camera_url = TRAINS_CONFIG.get(train_id, {}).get("rasp_url", "")

    return {
        "status": "success",
        "data": {
            "id": train_id,
            "name": train.name,
            "type": train.train_type,
            "connected": train.is_connected,
            "speed": train.speed,
            "section": train.section,
            "rgb": train.rgb,
            "telemetry_url": train.telemetry_url
        }
    }

@app.get("/config")
async def get_api_config():
    """Endpoint wymagany przez tablicę dworcową i system audio"""
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
                "section": t.section,
                "telemetry_url": t.telemetry_url
            } for tid, t in trains.items()
        },
        "zones": {
            z_id: (occ.name if hasattr(occ, 'name') else occ) if occ else None 
            for z_id, occ in dispatcher.zones.items()
        },
    }

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
