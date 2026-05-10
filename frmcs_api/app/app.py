from fastapi import FastAPI
import asyncio
import traceback
import os
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path

from app.lego_train import LegoTrain
from app.dispatcher import ZoneDispatcher, SystemLogger

# --- CONFIG & ENV ---
load_dotenv(Path(__file__).resolve().parent / ".env.local")

logger = SystemLogger(max_logs=10)
dispatcher = ZoneDispatcher(logger)

# Inicjalizacja pociągów
trains = {
    "express": LegoTrain("Express", os.getenv("EXPRESS_MAC", ""), "express"),
    "cargo": LegoTrain("Cargo", os.getenv("CARGO_MAC", ""), "cargo")
}

class SpeedRequest(BaseModel):
    speed: int

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for train in trains.values():
        if train.is_connected: await train.disconnect()

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
    return {
        "status": "success",
        "data": {
            "id": train_id,
            "name": train.name,
            "type": train.train_type,
            "connected": train.is_connected,
            "speed": train.speed,
            "section": train.section,
            "rgb": train.rgb
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
                "section": t.section
            } for tid, t in trains.items()
        },
        "zones": {z_id: occ for z_id, occ in dispatcher.zones.items()}
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
