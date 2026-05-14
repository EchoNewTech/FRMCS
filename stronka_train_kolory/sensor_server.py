import socket
import math
import time
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import board
import uvicorn

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

        # --- BME680 ---
        self.bme = None
        if self.i2c and adafruit_bme680:
            try:
                self.bme = adafruit_bme680.Adafruit_BME680_I2C(self.i2c, address=0x76)
                self.bme.sea_level_pressure = 1013.25 
            except Exception: pass

        # --- LSM6DS3 ---
        self.lsm = None
        if self.i2c and LSM6DS3:
            try:
                self.lsm = LSM6DS3(self.i2c)
            except Exception: pass

        # --- KOMPAS BMM150 ---
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

        # --- Zmienne do nawigacji inercyjnej (Całkowanie) ---
        self.last_time = time.time()
        self.velocity = [0.0, 0.0, 0.0] # Prędkość w m/s
        self.position = [0.0, 0.0, 0.0] # Pozycja (dystans) w metrach

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
                "velocity_m_s": None, 
                "position_m": None, 
                "total_position_m": None,
                "gyro_rad_s": None
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
                
                # Filtracja i usuwanie grawitacji Ziemi (założenie: czujnik leży płasko)
                az_comp = az - 9.81
                
                # Deadband (Ignorujemy mikroszumy, aby pociąg nie "jechał" w miejscu)
                deadband = 0.15
                if abs(ax) < deadband: ax = 0.0
                if abs(ay) < deadband: ay = 0.0
                if abs(az_comp) < deadband: az_comp = 0.0

                # 1. Całkowanie do PRĘDKOŚCI (v = v0 + a * dt)
                self.velocity[0] += ax * dt
                self.velocity[1] += ay * dt
                self.velocity[2] += az_comp * dt

                # Tłumik prędkości (Sztuczne hamowanie, zapobiega ucieczce w nieskończoność)
                self.velocity = [v * 0.98 for v in self.velocity]

                # 2. Całkowanie do POZYCJI (p = p0 + v * dt)
                self.position[0] += self.velocity[0] * dt
                self.position[1] += self.velocity[1] * dt
                self.position[2] += self.velocity[2] * dt

                # Obliczenie WYPADKOWEJ POZYCJI (Pitagoras przestrzenny)
                total_pos = math.sqrt(self.position[0]**2 + self.position[1]**2 + self.position[2]**2)
                
                data["motion"]["velocity_m_s"] = {"x": round(self.velocity[0], 2), "y": round(self.velocity[1], 2), "z": round(self.velocity[2], 2)}
                data["motion"]["position_m"] = {"x": round(self.position[0], 2), "y": round(self.position[1], 2), "z": round(self.position[2], 2)}
                data["motion"]["total_position_m"] = round(total_pos, 2)
                data["motion"]["gyro_rad_s"] = {"x": round(gx, 2), "y": round(gy, 2), "z": round(gz, 2)}
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

    def get_all_data(self):
        # Funkcja łącząca oba strumienie dla wstecznej kompatybilności z RPi 4
        return {**self.get_env_data(), **self.get_motion_data()}


# === INICJALIZACJA SERWERA ===
app = FastAPI()
sensors = TelemetrySensors()

# KOD HTML PANELU DIAGNOSTYCZNEGO
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RPi Zero - Czujniki</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white p-6 md:p-10 flex flex-col items-center min-h-screen">
    <h1 class="text-3xl font-bold text-green-500 mb-2 text-center flex items-center gap-3">
        <span class="w-3 h-3 rounded-full bg-green-500 animate-ping"></span>
        Węzeł Sensoryczny (RPi Zero)
    </h1>
    <p class="text-gray-400 text-sm mb-8">Ruch: 0.5s | Środowisko: 1.0s</p>

    <div class="w-full max-w-5xl grid grid-cols-1 md:grid-cols-3 gap-6">
        
        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg col-span-1 md:col-span-2 relative">
            <div class="absolute top-4 right-4 flex items-center gap-2">
                <span id="env-indicator" class="w-2 h-2 bg-blue-500 rounded-full transition-opacity duration-300"></span>
                <span class="text-[10px] text-gray-500 uppercase">1 Hz</span>
            </div>
            <h2 class="text-xl font-bold text-gray-300 border-b border-gray-600 pb-2 mb-4">Środowisko (BME680)</h2>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                <div class="bg-gray-900 p-3 rounded">
                    <span class="text-xs text-gray-500 uppercase block mb-1">Temperatura</span>
                    <span id="temp" class="text-2xl font-mono text-orange-400">-- °C</span>
                </div>
                <div class="bg-gray-900 p-3 rounded">
                    <span class="text-xs text-gray-500 uppercase block mb-1">Wilgotność</span>
                    <span id="hum" class="text-2xl font-mono text-blue-400">-- %</span>
                </div>
                <div class="bg-gray-900 p-3 rounded">
                    <span class="text-xs text-gray-500 uppercase block mb-1">Ciśnienie</span>
                    <span id="pres" class="text-2xl font-mono text-teal-400">-- hPa</span>
                </div>
                <div class="bg-gray-900 p-3 rounded">
                    <span class="text-xs text-gray-500 uppercase block mb-1">Gaz (kΩ)</span>
                    <span id="gas" class="text-2xl font-mono text-purple-400">-- kΩ</span>
                </div>
            </div>
        </div>

        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg text-center flex flex-col justify-center items-center relative">
            <div class="absolute top-4 right-4 flex items-center gap-2">
                <span id="comp-indicator" class="w-2 h-2 bg-red-500 rounded-full transition-opacity duration-300"></span>
                <span class="text-[10px] text-gray-500 uppercase">2 Hz</span>
            </div>
            <h2 class="text-xl font-bold text-gray-300 border-b border-gray-600 w-full pb-2 mb-4">Kompas v2.0</h2>
            <div id="compass-status" class="text-xs font-bold px-3 py-1 rounded bg-red-900 text-red-400 mb-4 uppercase">Nie wykryto</div>
            
            <div class="relative w-24 h-24 rounded-full border-4 border-gray-600 flex items-center justify-center">
                <span class="absolute top-1 text-xs font-bold text-gray-500">N</span>
                <span class="absolute bottom-1 text-xs font-bold text-gray-500">S</span>
                <span class="absolute left-1 text-xs font-bold text-gray-500">W</span>
                <span class="absolute right-1 text-xs font-bold text-gray-500">E</span>
                
                <div id="compass-needle" class="absolute w-1 h-16 bg-gradient-to-t from-transparent via-red-500 to-red-600 rounded-full transition-transform duration-100 origin-center" style="transform: rotate(0deg);"></div>
                <div class="w-3 h-3 bg-white rounded-full z-10"></div>
            </div>
            <div class="mt-4 text-xl font-mono text-yellow-400"><span id="heading-val">--</span>°</div>
        </div>

        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg col-span-1 md:col-span-3">
            <h2 class="text-xl font-bold text-gray-300 border-b border-gray-600 pb-2 mb-4">Ruch i Wibracje (LSM6DS3)</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="bg-gray-900 p-4 rounded text-center border-l-4 border-red-500">
                    <span class="text-xs text-gray-500 uppercase block mb-1">Siła Przyspieszenia (Wypadkowa)</span>
                    <span id="acc-total" class="text-3xl font-bold font-mono text-white block mb-3">-- <span class="text-sm text-gray-500 font-normal">m/s²</span></span>
                    <div class="flex justify-center gap-6 font-mono text-sm pt-2 border-t border-gray-700">
                        <span class="text-red-400">X: <span id="acc-x" class="text-white">--</span></span>
                        <span class="text-green-400">Y: <span id="acc-y" class="text-white">--</span></span>
                        <span class="text-blue-400">Z: <span id="acc-z" class="text-white">--</span></span>
                    </div>
                </div>
                <div class="bg-gray-900 p-4 rounded text-center border-l-4 border-blue-500">
                    <span class="text-xs text-gray-500 uppercase block mb-3">Żyroskop (Rotacja rad/s)</span>
                    <div class="flex justify-center items-center h-full pb-6 gap-8 font-mono text-lg">
                        <span class="text-red-400">X: <span id="gyr-x" class="text-white">--</span></span>
                        <span class="text-green-400">Y: <span id="gyr-y" class="text-white">--</span></span>
                        <span class="text-blue-400">Z: <span id="gyr-z" class="text-white">--</span></span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Funkcja mrugania kropkami informującymi o pobraniu danych
        function flashIndicator(id) {
            const el = document.getElementById(id);
            el.style.opacity = '1';
            setTimeout(() => el.style.opacity = '0.2', 150);
        }

        // POBIERANIE RUCHU CO 0.5 SEKUNDY (Kompas + Akcelerometr)
        async function fetchMotion() {
            try {
                const response = await fetch('/api/telemetry/motion');
                const data = await response.json();
                flashIndicator('comp-indicator');
                
                // Kompas
                const comp = data.compass;
                const compStatus = document.getElementById('compass-status');
                if (comp.detected) {
                    compStatus.innerText = "Aktywny (I2C: 0x13)";
                    compStatus.className = "text-xs font-bold px-3 py-1 rounded bg-green-900 text-green-400 mb-4 uppercase";
                    if (comp.heading_deg !== null) {
                        document.getElementById('heading-val').innerText = comp.heading_deg;
                        document.getElementById('compass-needle').style.transform = `rotate(${comp.heading_deg}deg)`;
                    }
                }

                // Akcelerometr i Żyroskop
                const mot = data.motion;
                if (mot.accel_m_s2 !== null) {
                    document.getElementById('acc-total').innerText = mot.total_accel.toFixed(2);
                    document.getElementById('acc-x').innerText = mot.accel_m_s2.x;
                    document.getElementById('acc-y').innerText = mot.accel_m_s2.y;
                    document.getElementById('acc-z').innerText = mot.accel_m_s2.z;
                    
                    document.getElementById('gyr-x').innerText = mot.gyro_rad_s.x;
                    document.getElementById('gyr-y').innerText = mot.gyro_rad_s.y;
                    document.getElementById('gyr-z').innerText = mot.gyro_rad_s.z;
                }
            } catch (e) {}
        }

        // POBIERANIE ŚRODOWISKA CO 1.0 SEKUNDĘ (BME680)
        async function fetchEnvironment() {
            try {
                const response = await fetch('/api/telemetry/env');
                const data = await response.json();
                flashIndicator('env-indicator');
                
                const env = data.environment;
                if (env.temperature_c !== null) {
                    document.getElementById('temp').innerText = env.temperature_c + ' °C';
                    document.getElementById('hum').innerText = env.humidity_percent + ' %';
                    document.getElementById('pres').innerText = env.pressure_hpa + ' hPa';
                    document.getElementById('gas').innerText = (env.gas_ohms / 1000).toFixed(1) + ' kΩ';
                }
            } catch (e) {}
        }

        // Ustawienie niezależnych pętli czasowych
        setInterval(fetchMotion, 500);       // Ruch co 500ms
        setInterval(fetchEnvironment, 1000); // Środowisko co 1000ms
        
        // Pierwsze pobranie od razu
        fetchMotion();
        fetchEnvironment();
    </script>
</body>
</html>
"""

# --- GŁÓWNE ENDPOINTY API ---

@app.get("/", response_class=HTMLResponse)
def index():
    """Zwraca stronę HTML Panelu Diagnostycznego"""
    return HTML_TEMPLATE

@app.get("/api/telemetry")
def get_telemetry():
    """Pełen zrzut danych (Dla pociągów RPi 4)"""
    return sensors.get_all_data()

@app.get("/api/telemetry/env")
def get_telemetry_env():
    """Tylko dane środowiskowe (Dla skryptu JS - 1s)"""
    return sensors.get_env_data()

@app.get("/api/telemetry/motion")
def get_telemetry_motion():
    """Tylko dane o ruchu (Dla skryptu JS - 0.5s)"""
    return sensors.get_motion_data()


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
    print(" Uruchamiam serwer czujników na porcie 8002...")
    print(f" Otwórz panel diagnostyczny: http://{local_ip}:8002")
    print("="*55 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8002, access_log=False)
