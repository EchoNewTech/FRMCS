import socket
import math
import time
import subprocess
import uvicorn
import board
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse

# Próby importu bibliotek sprzętowych
try:
    import adafruit_bme680
except ImportError:
    adafruit_bme680 = None

try:
    from adafruit_lsm6ds.lsm6ds3 import LSM6DS3
except ImportError:
    LSM6DS3 = None

class TelemetrySensors:
    def __init__(self):
        print("[SENSORY] Inicjalizacja magistrali I2C...")
        try:
            self.i2c = board.I2C()
        except Exception as e:
            print(f"[SENSORY] Błąd sprzętowy I2C: {e}")
            self.i2c = None

        self.bme = None
        if self.i2c and adafruit_bme680:
            try:
                self.bme = adafruit_bme680.Adafruit_BME680_I2C(self.i2c, address=0x76)
                self.bme.sea_level_pressure = 1013.25 
            except Exception: pass

        self.lsm = None
        if self.i2c and LSM6DS3:
            try:
                self.lsm = LSM6DS3(self.i2c)
            except Exception: pass

        self.compass_detected = False
        try:
            import smbus2
            self.bus = smbus2.SMBus(1)
            self.bus.read_byte_data(0x13, 0x40) 
            self.bus.write_byte_data(0x13, 0x4B, 0x01) 
            time.sleep(0.01)
            self.bus.write_byte_data(0x13, 0x4C, 0x00) 
            self.compass_detected = True
        except Exception: pass

        self.last_time = time.time()
        self.accel_offset = [0.0, 0.0, 0.0]
        self.velocity = [0.0, 0.0, 0.0]
        self.position = [0.0, 0.0, 0.0]
        self.calibrate_accelerometer()

    def calibrate_accelerometer(self):
        if self.lsm:
            ox, oy, oz = 0.0, 0.0, 0.0
            valid_samples = 0
            for _ in range(50):
                try:
                    x, y, z = self.lsm.acceleration
                    ox += x; oy += y; oz += z
                    valid_samples += 1
                except Exception: pass
                time.sleep(0.02)
            if valid_samples > 0:
                self.accel_offset = [ox / valid_samples, oy / valid_samples, oz / valid_samples]
        
        self.velocity = [0.0, 0.0, 0.0]
        self.position = [0.0, 0.0, 0.0]
        self.last_time = time.time()

    def get_env_data(self):
        data = {"environment": {"temperature_c": None, "humidity_percent": None, "pressure_hpa": None, "gas_ohms": None}}
        if self.bme:
            try:
                data["environment"]["temperature_c"] = round(self.bme.temperature, 2)
                data["environment"]["humidity_percent"] = round(self.bme.humidity, 2)
                data["environment"]["pressure_hpa"] = round(self.bme.pressure, 2)
                data["environment"]["gas_ohms"] = round(self.bme.gas, 2)
            except Exception: pass
        return data

    def get_motion_data(self):
        data = {
            "motion": {
                "accel_filtered_m_s2": None, "total_accel_m_s2": None,
                "velocity_m_s": None, "total_velocity_km_h": None,
                "position_m": None, "total_position_m": None,
                "gyro_rad_s": None, "total_gyro_rad_s": None
            },
            "compass": {"detected": self.compass_detected, "heading_deg": None}
        }
        
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time

        if self.lsm:
            try:
                ax, ay, az = self.lsm.acceleration
                gx, gy, gz = self.lsm.gyro
                ax_comp = ax - self.accel_offset[0]
                ay_comp = ay - self.accel_offset[1]
                az_comp = az - self.accel_offset[2]
                
                deadband = 0.35
                ax_comp = 0.0 if abs(ax_comp) < deadband else ax_comp
                ay_comp = 0.0 if abs(ay_comp) < deadband else ay_comp
                az_comp = 0.0 if abs(az_comp) < deadband else az_comp

                total_accel = math.sqrt(ax_comp**2 + ay_comp**2 + az_comp**2)

                for i, val in enumerate([ax_comp, ay_comp, az_comp]):
                    self.velocity[i] += val * dt
                    self.velocity[i] *= 0.95 # Tłumienie dryftu
                    self.position[i] += self.velocity[i] * dt

                total_vel = math.sqrt(sum(v**2 for v in self.velocity))
                total_pos = math.sqrt(sum(p**2 for p in self.position))
                total_gyro = math.sqrt(gx**2 + gy**2 + gz**2)
                
                data["motion"].update({
                    "accel_filtered_m_s2": {"x": round(ax_comp, 2), "y": round(ay_comp, 2), "z": round(az_comp, 2)},
                    "total_accel_m_s2": round(total_accel, 2),
                    "velocity_m_s": {"x": round(self.velocity[0], 2), "y": round(self.velocity[1], 2), "z": round(self.velocity[2], 2)},
                    "total_velocity_km_h": round(total_vel * 3.6, 2),
                    "position_m": {"x": round(self.position[0], 2), "y": round(self.position[1], 2), "z": round(self.position[2], 2)},
                    "total_position_m": round(total_pos, 2),
                    "gyro_rad_s": {"x": round(gx, 2), "y": round(gy, 2), "z": round(gz, 2)},
                    "total_gyro_rad_s": round(total_gyro, 2)
                })
            except Exception: pass

        if self.compass_detected:
            try:
                data_bytes = self.bus.read_i2c_block_data(0x13, 0x42, 6)
                x = (data_bytes[1] << 5) | (data_bytes[0] >> 3)
                if x > 4095: x -= 8192
                y = (data_bytes[3] << 5) | (data_bytes[2] >> 3)
                if y > 4095: y -= 8192
                heading = math.atan2(y, x) * (180.0 / math.pi)
                if heading < 0: heading += 360
                data["compass"]["heading_deg"] = int(heading)
            except Exception: pass
            
        return data

# --- LOGIKA KAMERY ---
def generate_frames():
    cmd = [
        "rpicam-vid", "-t", "0", "--codec", "mjpeg", "--width", "480", "--height", "360",
        "--framerate", "30", "-q", "40", "--inline", "-o", "-"
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    stream = b''
    try:
        while True:
            chunk = process.stdout.read(4096)
            if not chunk: break
            stream += chunk
            start = stream.find(b'\xff\xd8')
            end = stream.find(b'\xff\xd9')
            if start != -1 and end != -1:
                jpg = stream[start:end+2]
                stream = stream[end+2:]
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')
    except Exception:
        process.terminate()
    finally:
        process.terminate()

# --- SERWER ---
app = FastAPI()
sensors = TelemetrySensors()

# --- TEMPLATKA INTERFEJSU (ZMNIEJSZONE ELEMENTY) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RPi Telemetry HUD</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0a0a0c; }
        .video-container { 
            position: relative; 
            overflow: hidden; 
            border-radius: 0.5rem; 
            border: 1px solid #1f2937; 
            background: #000; 
            max-width: 540px; /* Zmniejszona szerokość kamery */
            margin: 0 auto; 
        }
        .video-overlay { 
            position: absolute; top: 0; left: 0; width: 100%; height: 100%; 
            pointer-events: none; border: 10px solid transparent; 
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.05) 50%), 
                        linear-gradient(90deg, rgba(255, 0, 0, 0.02), rgba(0, 255, 0, 0.01), rgba(0, 0, 255, 0.02)); 
            background-size: 100% 2px, 3px 100%; 
        }
        .scanline { 
            width: 100%; height: 1px; background: rgba(0, 255, 0, 0.1); 
            position: absolute; animation: scan 4s linear infinite; 
        }
        @keyframes scan { from { top: 0; } to { top: 100%; } }
        .data-card { background: rgba(31, 41, 55, 0.4); backdrop-filter: blur(4px); }
    </style>
</head>
<body class="text-gray-300 p-4 md:p-6 flex flex-col items-center min-h-screen font-sans">
    
    <header class="w-full max-w-5xl flex justify-between items-center mb-4 border-b border-gray-800 pb-2">
        <div class="flex items-center gap-3">
            <div class="w-2 h-2 rounded-full bg-red-600 animate-pulse"></div>
            <h1 class="text-sm font-black tracking-widest uppercase text-green-500">System Telemetryczny v3.1</h1>
        </div>
        <div class="text-[10px] font-mono text-gray-500 uppercase">Status: Connected // Stream: Active</div>
    </header>

    <div class="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-12 gap-4">
        
        <div class="lg:col-span-7 flex flex-col gap-4">
            <div class="video-container shadow-2xl">
                <div class="scanline"></div>
                <div class="video-overlay"></div>
                <div class="absolute top-2 left-2 z-10 bg-black/60 px-2 py-0.5 rounded text-[9px] font-mono text-green-400 border border-green-500/30">
                    CAM_01 // MJPEG_480P
                </div>
                <img src="/video" class="w-full h-auto block" alt="Strumień wideo">
            </div>
            
            <div class="data-card p-3 rounded-lg border border-gray-800 shadow-sm">
                <div class="flex justify-between items-center mb-2">
                    <h2 class="text-[10px] font-bold uppercase tracking-tighter text-gray-500">Inertial Navigation</h2>
                    <button onclick="resetPosition(this)" class="bg-red-900/20 hover:bg-red-900/40 text-red-500 text-[9px] font-bold py-1 px-3 rounded border border-red-500/30 transition-all">ZERUJ SENSORY</button>
                </div>
                <div class="grid grid-cols-4 gap-2">
                    <div class="text-center p-1 border-r border-gray-700/50">
                        <span class="text-[8px] text-gray-500 block">ACCEL</span>
                        <span id="acc-total" class="text-base font-mono text-yellow-500">0.00</span>
                    </div>
                    <div class="text-center p-1 border-r border-gray-700/50">
                        <span class="text-[8px] text-gray-500 block">SPEED</span>
                        <span id="vel-total-kmh" class="text-base font-mono text-blue-500">0.00</span>
                    </div>
                    <div class="text-center p-1 border-r border-gray-700/50">
                        <span class="text-[8px] text-gray-500 block">DIST</span>
                        <span id="pos-total" class="text-base font-mono text-purple-500">0.00</span>
                    </div>
                    <div class="text-center p-1">
                        <span class="text-[8px] text-gray-500 block">GYRO</span>
                        <span id="gyr-total" class="text-base font-mono text-green-500">0.00</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="lg:col-span-5 flex flex-col gap-4">
            
            <div class="data-card p-4 rounded-lg border border-gray-800 relative overflow-hidden">
                <div id="env-indicator" class="absolute top-0 right-0 w-1 h-full bg-blue-500 opacity-10 transition-opacity"></div>
                <h2 class="text-[10px] font-bold text-gray-500 uppercase mb-3">Atmospheric Sensors</h2>
                <div class="grid grid-cols-2 gap-4">
                    <div class="flex flex-col border-l-2 border-orange-500/50 pl-2">
                        <span class="text-[9px] text-gray-500 uppercase">Temperatura</span>
                        <span id="temp" class="text-lg font-mono text-orange-400">-- °C</span>
                    </div>
                    <div class="flex flex-col border-l-2 border-blue-500/50 pl-2">
                        <span class="text-[9px] text-gray-500 uppercase">Wilgotność</span>
                        <span id="hum" class="text-lg font-mono text-blue-400">-- %</span>
                    </div>
                    <div class="flex flex-col border-l-2 border-teal-500/50 pl-2">
                        <span class="text-[9px] text-gray-500 uppercase">Ciśnienie</span>
                        <span id="pres" class="text-base font-mono text-teal-400">-- hPa</span>
                    </div>
                    <div class="flex flex-col border-l-2 border-purple-500/50 pl-2">
                        <span class="text-[9px] text-gray-500 uppercase">Jakość Pow.</span>
                        <span id="gas" class="text-base font-mono text-purple-400">-- kΩ</span>
                    </div>
                </div>
            </div>

            <div class="data-card p-4 rounded-lg border border-gray-800 flex flex-col items-center">
                <h2 class="text-[10px] font-bold text-gray-500 uppercase mb-4 self-start">Digital Compass</h2>
                <div class="relative w-28 h-28 rounded-full border border-gray-700 bg-black/40 shadow-[inset_0_0_10px_rgba(0,0,0,0.5)]">
                    <div class="absolute inset-0 flex items-center justify-center text-[8px] text-gray-600 font-bold">
                        <span class="absolute top-1">N</span>
                        <span class="absolute bottom-1">S</span>
                        <span class="absolute left-1">W</span>
                        <span class="absolute right-1">E</span>
                    </div>
                    <div id="compass-needle" class="absolute inset-0 flex items-center justify-center transition-transform duration-500 ease-out">
                        <div class="w-0.5 h-12 bg-gradient-to-t from-transparent via-red-500 to-red-500 rounded-full shadow-[0_0_5px_red]"></div>
                    </div>
                    <div class="absolute inset-0 flex items-center justify-center">
                        <div class="w-1.5 h-1.5 bg-white rounded-full shadow-white shadow-sm"></div>
                    </div>
                </div>
                <div class="mt-3 text-2xl font-mono text-yellow-500"><span id="heading-val">--</span>°</div>
            </div>

        </div>
    </div>

    <script>
        function flashIndicator(id) {
            const el = document.getElementById(id);
            if(el) {
                el.style.opacity = '0.5';
                setTimeout(() => el.style.opacity = '0.1', 200);
            }
        }

        async function resetPosition(btn) {
            const originalText = btn.innerText;
            btn.innerText = "KALIBRACJA...";
            btn.disabled = true;
            try { await fetch('/api/telemetry/reset', {method: 'POST'}); } catch (e) {}
            setTimeout(() => { 
                btn.innerText = originalText; 
                btn.disabled = false;
            }, 2000);
        }

        async function updateData() {
            try {
                const [resMotion, resEnv] = await Promise.all([
                    fetch('/api/telemetry/motion'),
                    fetch('/api/telemetry/env')
                ]);
                
                const motion = await resMotion.json();
                const env = await resEnv.json();

                if (motion.motion.total_accel_m_s2 !== null) {
                    document.getElementById('acc-total').innerText = motion.motion.total_accel_m_s2.toFixed(2);
                    document.getElementById('vel-total-kmh').innerText = motion.motion.total_velocity_km_h.toFixed(2);
                    document.getElementById('pos-total').innerText = motion.motion.total_position_m.toFixed(2);
                    document.getElementById('gyr-total').innerText = motion.motion.total_gyro_rad_s.toFixed(2);
                }

                if (motion.compass.detected && motion.compass.heading_deg !== null) {
                    document.getElementById('heading-val').innerText = motion.compass.heading_deg;
                    document.getElementById('compass-needle').style.transform = `rotate(${motion.compass.heading_deg}deg)`;
                }

                if (env.environment.temperature_c !== null) {
                    flashIndicator('env-indicator');
                    document.getElementById('temp').innerText = env.environment.temperature_c + ' °C';
                    document.getElementById('hum').innerText = env.environment.humidity_percent + ' %';
                    document.getElementById('pres').innerText = env.environment.pressure_hpa + ' hPa';
                    document.getElementById('gas').innerText = (env.environment.gas_ohms / 1000).toFixed(1) + ' kΩ';
                }
            } catch (e) { console.error("Błąd pobierania danych", e); }
        }

        setInterval(updateData, 500);
        updateData();
    </script>
</body>
</html>
"""

# --- ENDPOINTY FASTAPI ---

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_TEMPLATE

@app.get("/api/telemetry/env")
def get_telemetry_env():
    return sensors.get_env_data()

@app.get("/api/telemetry/motion")
def get_telemetry_motion():
    return sensors.get_motion_data()

@app.post("/api/telemetry/reset")
def reset_telemetry():
    sensors.calibrate_accelerometer()
    return {"status": "reset_complete"}

@app.get("/video")
def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# --- URUCHOMIENIE SERWERA ---

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception: return "127.0.0.1"

if __name__ == "__main__":
    ip = get_local_ip()
    print("-" * 50)
    print(f" PANEL KONTROLNY AKTYWNY")
    print(f" ADRES: http://{ip}:8002")
    print("-" * 50)
    # Wyłączenie logów uvicorn dla czystości konsoli
    uvicorn.run(app, host="0.0.0.0", port=8002, access_log=False)
