import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
import uvicorn
from lego_train import LegoTrain

EXPRESS_MAC = "9C:9A:C0:18:86:E1"
CARGO_MAC = "9C:9A:C0:1A:7A:AF"
BASE_DIR = Path(__file__).parent

trains = {
    "express": LegoTrain("Express", EXPRESS_MAC),
    "cargo": LegoTrain("Cargo", CARGO_MAC)
}

@asynccontextmanager
async def lifespan(_: FastAPI):
    asyncio.create_task(trains["express"].connect())
    asyncio.create_task(trains["cargo"].connect())
    yield
    for t in trains.values():
        if t.client and t.client.is_connected:
            await t.send_speed(0)
            await t.client.disconnect()

app = FastAPI(lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def index():
    path = BASE_DIR / "index.html"
    if not path.exists():
        raise HTTPException(404, "Index file not found")
    return path.read_text(encoding="utf-8")

@app.post("/api/connect/{tid}")
async def api_connect(tid: str):
    if tid not in trains:
        raise HTTPException(404)
    status_conn = await trains[tid].connect()
    return {"status": "success" if status_conn else "failed"}

@app.post("/api/move/{tid}/{direction}")
async def api_move(tid: str, direction: str):
    t = trains.get(tid)
    if not t:
        raise HTTPException(404)
    
    # Sprawdzenie połączenia przed ruchem
    if not t.client or not t.client.is_connected:
        raise HTTPException(status_code=412, detail="Pociąg nie jest połączony")

    new_speed = t.speed + (10 if direction == "up" else -10)
    await t.send_speed(new_speed)
    return {"speed": t.speed}

@app.post("/api/stop/{tid}")
async def api_stop(tid: str):
    t = trains.get(tid)
    if not t:
        raise HTTPException(404)

    # Sprawdzenie połączenia przed zatrzymaniem
    if not t.client or not t.client.is_connected:
        raise HTTPException(status_code=412, detail="Pociąg nie jest połączony")

    await t.stop()
    return {"status": "stopped", "speed": 0}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)