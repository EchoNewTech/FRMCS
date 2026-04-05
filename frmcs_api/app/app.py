from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.lego_train import LegoTrain
from app.ble_manager import BLEManager



# MAC
EXPRESS_MAC = "9C:9A:C0:18:86:E1"
CARGO_MAC = "9C:9A:C0:1A:7A:AF"

express = LegoTrain("Express", EXPRESS_MAC, 0)
cargo = LegoTrain("Cargo", CARGO_MAC, 20)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # START
    print("Starting app...")

    yield

    # STOP
    print("Stopping app...")

    if express.client and express.client.is_connected:
        await express.client.disconnect()
    
    if cargo.client and cargo.client.is_connected:
        await cargo.stop()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Test
@app.get("/")
def home():
    return {"message": "FRMCS API"}


# Connect
@app.post("/express/connect")
async def connect_express():
    try:
        await express.connect()
        return {"status": "express connected"}

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/cargo/connect")
async def connect_cargo():
    try:
        await cargo.connect()
        return {"status": "cargo connected"}

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# speed
@app.post("/express/speed")
async def express_speed(speed: int):
    if not express.client or not express.client.is_connected:
        await express.connect()

    await express.send_speed(speed)
    return {"express_speed": speed}


@app.post("/cargo/speed")
async def cargo_speed(speed: int):
    if not cargo.client or not cargo.client.is_connected:
        await cargo.connect()

    await cargo.send_speed(speed)
    return {"cargo_speed": speed}


# stop
@app.post("/express/stop")
async def express_stop():
    await express.stop()
    return {"status": "express stopped"}


@app.post("/cargo/stop")
async def cargo_stop():
    await cargo.stop()
    return {"status": "cargo stopped"}


# disconnect
@app.post("/express/disconnect")
async def express_disconnect():
    if express.client and express.client.is_connected:
        await express.disconnect()
        return {"status": "express disconnected"}
    return {"status": "already disconnected"}


@app.post("/cargo/disconnect")
async def cargo_disconnect():
    if cargo.client and cargo.client.is_connected:
        await cargo.disconnect()
        return {"status": "cargo disconnected"}
    return {"status": "already disconnected"}


# status
@app.get("/status")
async def status():
    return {
        "express": {
            "speed": express.speed,
            "connected": express.client.is_connected if express.client else False
        },
        "cargo": {
            "speed": cargo.speed,
            "connected": cargo.client.is_connected if cargo.client else False
        }
    }