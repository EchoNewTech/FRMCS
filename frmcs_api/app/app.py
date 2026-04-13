from fastapi import FastAPI
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from dotenv import load_dotenv
import os

from app.lego_train import LegoTrain
from app.ble_manager import BLEManager


load_dotenv(".env.local")

# MAC
EXPRESS_MAC = os.getenv("EXPRESS_MAC")
CARGO_MAC = os.getenv("CARGO_MAC")

express = LegoTrain("Express", EXPRESS_MAC, 0)
cargo = LegoTrain("Cargo", CARGO_MAC, 20)


class SpeedRequest(BaseModel):
    speed: int

class LightRequest(BaseModel):
    brightness: int



@asynccontextmanager
async def lifespan(app: FastAPI):
    # START
    print("Starting app...")

    yield

    # STOP
    print("Stopping app...")

    if express.client and express.client.is_connected:
        await express.disconnect() # express.client.disconnect()
    
    if cargo.client and cargo.client.is_connected:
        await cargo.disconnect() # cargo.stop()


app = FastAPI(lifespan=lifespan)

cors_origins = os.getenv("CORS_ORIGINS", "").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Test
@app.get("/")
def home():
    return {"status": "success", "message": "FRMCS API"}


# Connect
@app.post("/express/connect")
async def connect_express():
    try:
        await express.connect()
        await asyncio.sleep(1)
        return {"status": "success", "message": "express connected"}

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/cargo/connect")
async def connect_cargo():
    try:
        await cargo.connect()
        await asyncio.sleep(1)
        return {"status": "success", "message": "cargo connected"}

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# speed
@app.post("/express/speed")
async def express_speed(req: SpeedRequest):
    try:
        print("Incoming speed:", req.speed)
        if not express.client or not express.client.is_connected:
            await express.connect()

        await express.send_speed(req.speed)

        return {"status": "success", "speed": req.speed}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/cargo/speed")
async def cargo_speed(req: SpeedRequest):
    try:
        print("Incoming speed:", req.speed)
        if not cargo.client or not cargo.client.is_connected:
            await cargo.connect()

        await cargo.send_speed(req.speed)

        return {"status": "success", "speed": req.speed}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# stop
@app.post("/express/stop")
async def express_stop():
    try:
        await express.stop()
        return {"status": "success", "message": "express stopped"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/cargo/stop")
async def cargo_stop():
    try:
        await cargo.stop()
        return {"status": "success", "message": "cargo stopped"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# disconnect
@app.post("/express/disconnect")
async def express_disconnect():
    try:
        if express.client and express.client.is_connected:
            await express.stop()
            await express.disconnect()
            return {"status": "success", "message": "express disconnected"}
        return {"status": "success", "message": "already disconnected"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/cargo/disconnect")
async def cargo_disconnect():
    try:
        if cargo.client and cargo.client.is_connected:
            await cargo.stop()
            await cargo.disconnect()
            return {"status": "success", "message": "cargo disconnected"}
        return {"status": "success", "message": "already disconnected"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# lights
@app.post("/express/light")
async def express_light(req: LightRequest):
    return await express.set_light(req.brightness)



# status
@app.get("/status")
async def status():
    try:
        return {
            "status": "success",
            "data": {
                "express": {
                    "speed": express.speed,
                    "connected": express.client.is_connected if express.client else False,
                    "light": getattr(express, "light_on", False)
                },
                "cargo": {
                    "speed": cargo.speed,
                    "connected": cargo.client.is_connected if cargo.client else False
                }
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

