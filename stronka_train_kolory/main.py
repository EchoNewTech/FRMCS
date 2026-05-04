import socket
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn

from train import LegoTrain
from sensor import ColorDetector
from dispatcher import SystemLogger, ZoneDispatcher
from config import TRAINS_CONFIG, COLORS_CONFIG

BASE_DIR = Path(__file__).parent

logger = SystemLogger(max_logs=8)
dispatcher = ZoneDispatcher(logger)

# Automatyczne dodawanie pociągów z konfiguracji
trains = {
    tid: LegoTrain(tinfo["name"], tinfo["mac"]) for tid, tinfo in TRAINS_CONFIG.items()
}

@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    for t in trains.values():
        if getattr(t, 'client', None) and t.client.is_connected:
            await t.set_speed(0)
            await t.client.disconnect()

app = FastAPI(lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def index():
    path = BASE_DIR / "index.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Plik index.html nie istnieje")
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
async def api_simulate_color(tid: str, color_code: int):
    t = trains.get(tid)
    if t and getattr(t, 'detector', None):
        await t.detector.handle_color(color_code)
        return {"status": "simulated"}
    raise HTTPException(status_code=400, detail="Brak detektora")

@app.get("/api/status")
async def api_status():
    data = {
        "logs": logger.logs,
        "trains": {},
        "zones": {
            z_id: dispatcher.zones[z_id].name if dispatcher.zones.get(z_id) else None
            for z_id in dispatcher.zones
        }
    }
    for tid, t in trains.items():
        conn_type = None
        if getattr(t, 'is_virtual', False):
            conn_type = "virtual"
        elif getattr(t, 'client', None) and t.client.is_connected:
            conn_type = "bt"

        code = getattr(t.detector, 'last_color_code', -1) if getattr(t, 'detector', None) else -1
        ui_color = COLORS_CONFIG.get(code, {}).get("ui_color", "gray")
        
        # --- POBRANIE TELEMETRII RGB ---
        rgb_data = getattr(t.detector, 'last_rgb', {"r": 0, "g": 0, "b": 0}) if getattr(t, 'detector', None) else {"r": 0, "g": 0, "b": 0}

        data["trains"][tid] = {
            "speed": t.speed,
            "color_text": t.detector.status_text if getattr(t, 'detector', None) else "BRAK_INFO",
            "ui_color": ui_color,
            "connection": conn_type,
            "rgb": rgb_data  # <--- NOWA LINIA: Wysyłamy RGB do HTMLa
        }
    return data

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    print("\n" + "="*55)
    print(" SYSTEM FRMCS JEST GOTOWY!")
    print(f" Otwórz panel sterowania: http://{local_ip}:8000")
    print("="*55 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)