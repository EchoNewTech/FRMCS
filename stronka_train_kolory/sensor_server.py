import socket
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import board
import uvicorn
import time
import math

# Próba importu bibliotek z obsługą błędów
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

        # --- 1. BME680 (Adres wymuszony na 0x76 na podstawie i2cdetect) ---
        self.bme = None
        if self.i2c and adafruit_bme680:
            try:
                self.bme = adafruit_bme680.Adafruit_BME680_I2C(self.i2c, address=0x76)
                self.bme.sea_level_pressure = 1013.25 
                print("[SENSORY] BME680 podłączony poprawnie (0x76).")
            except Exception as e:
                print(f"[SENSORY] Nie znaleziono BME680 na I2C (0x76): {e}")

        # --- 2. LSM6DS3 (Akcelerometr, Żyroskop) ---
        self.lsm = None
        if self.i2c and LSM6DS3:
            try:
                self.lsm = LSM6DS3(self.i2c)
                print("[SENSORY] LSM6DS3 podłączony poprawnie (0x6a).")
            except Exception as e:
                print(f"[SENSORY] Nie znaleziono LSM6DS3 na I2C: {e}")

        # --- 3. Kompas Grove 3-Axis v2.0 (BMM150) ---
        self.compass_detected = False
        try:
            import smbus2
            self.bus = smbus2.SMBus(1)
            
            # Wzbudzanie kompasu BMM150 z trybu uśpienia
            self.bus.read_byte_data(0x13, 0x40) # Sprawdzenie czy żyje
            self.bus.write_byte_data(0x13, 0x4B, 0x01) # Power ON (Włącz zasilanie)
            time.sleep(0.01)
            self.bus.write_byte_data(0x13, 0x4C, 0x00) # Tryb normalny (Ciągły pomiar)
            
            self.compass_detected = True
            print("[SENSORY] Kompas BMM150 wybudzony i działa (0x13).")
        except Exception as e:
            print(f"[SENSORY] Błąd inicjalizacji kompasu: {e}")

    def get_all_data(self):
        data = {
            "environment": {"temperature_c": None, "humidity_percent": None, "pressure_hpa": None, "gas_ohms": None},
            "motion": {"accel_m_s2": None, "gyro_rad_s": None},
            "compass": {"detected": self.compass_detected, "heading_deg": None}
        }

        if self.bme:
            try:
                data["environment"]["temperature_c"] = round(self.bme.temperature, 2)
                data["environment"]["humidity_percent"] = round(self.bme.humidity, 2)
                data["environment"]["pressure_hpa"] = round(self.bme.pressure, 2)
                data["environment"]["gas_ohms"] = round(self.bme.gas, 2)
            except Exception: pass

        if self.lsm:
            try:
                accel_x, accel_y, accel_z = self.lsm.acceleration
                gyro_x, gyro_y, gyro_z = self.lsm.gyro
                data["motion"]["accel_m_s2"] = {"x": round(accel_x, 2), "y": round(accel_y, 2), "z": round(accel_z, 2)}
                data["motion"]["gyro_rad_s"] = {"x": round(gyro_x, 2), "y": round(gyro_y, 2), "z": round(gyro_z, 2)}
            except Exception: pass

        if self.compass_detected:
            try:
                # Odczyt 6 surowych bajtów danych magnetycznych z osi X i Y
                data_bytes = self.bus.read_i2c_block_data(0x13, 0x42, 6)
                
                # BMM150 przesyła dane w specjalnym 13-bitowym formacie. Trzeba je połączyć.
                x = (data_bytes[1] << 5) | (data_bytes[0] >> 3)
                if x > 4095: x -= 8192  # Zamiana na wartości ujemne (Two's complement)
                
                y = (data_bytes[3] << 5) | (data_bytes[2] >> 3)
                if y > 4095: y -= 8192

                # Obliczenie realnego kąta (heading) na podstawie pola magnetycznego
                heading = math.atan2(y, x) * (180.0 / math.pi)
                if heading < 0:
                    heading += 360
                    
                data["compass"]["heading_deg"] = int(heading)
            except Exception: 
                pass

        return data

# === INICJALIZACJA SERWERA ===
app = FastAPI()
sensors = TelemetrySensors()

# KOD HTML PANELU DIAGNOSTYCZNEGO (DODANO KOMPAS)
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
    <p class="text-gray-400 text-sm mb-8">Odświeżanie na żywo co 0.5 sekundy</p>

    <div class="w-full max-w-5xl grid grid-cols-1 md:grid-cols-3 gap-6">
        
        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg col-span-1 md:col-span-2">
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

        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg text-center flex flex-col justify-center items-center">
            <h2 class="text-xl font-bold text-gray-300 border-b border-gray-600 w-full pb-2 mb-4">Kompas v2.0</h2>
            <div id="compass-status" class="text-xs font-bold px-3 py-1 rounded bg-red-900 text-red-400 mb-4 uppercase">Nie wykryto</div>
            
            <div class="relative w-24 h-24 rounded-full border-4 border-gray-600 flex items-center justify-center">
                <span class="absolute top-1 text-xs font-bold text-gray-500">N</span>
                <span class="absolute bottom-1 text-xs font-bold text-gray-500">S</span>
                <span class="absolute left-1 text-xs font-bold text-gray-500">W</span>
                <span class="absolute right-1 text-xs font-bold text-gray-500">E</span>
                
                <div id="compass-needle" class="absolute w-1 h-16 bg-gradient-to-t from-transparent via-red-500 to-red-600 rounded-full transition-transform duration-300 origin-center" style="transform: rotate(0deg);"></div>
                
                <div class="w-3 h-3 bg-white rounded-full z-10"></div>
            </div>
            <div class="mt-4 text-xl font-mono text-yellow-400"><span id="heading-val">--</span>°</div>
        </div>

        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg col-span-1 md:col-span-3">
            <h2 class="text-xl font-bold text-gray-300 border-b border-gray-600 pb-2 mb-4">Ruch i Wibracje (LSM6DS3)</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="bg-gray-900 p-4 rounded text-center">
                    <span class="text-xs text-gray-500 uppercase block mb-3">Akcelerometr (m/s²)</span>
                    <div class="flex justify-center gap-8 font-mono text-lg">
                        <span class="text-red-400">X: <span id="acc-x" class="text-white">--</span></span>
                        <span class="text-green-400">Y: <span id="acc-y" class="text-white">--</span></span>
                        <span class="text-blue-400">Z: <span id="acc-z" class="text-white">--</span></span>
                    </div>
                </div>
                <div class="bg-gray-900 p-4 rounded text-center">
                    <span class="text-xs text-gray-500 uppercase block mb-3">Żyroskop (rad/s)</span>
                    <div class="flex justify-center gap-8 font-mono text-lg">
                        <span class="text-red-400">X: <span id="gyr-x" class="text-white">--</span></span>
                        <span class="text-green-400">Y: <span id="gyr-y" class="text-white">--</span></span>
                        <span class="text-blue-400">Z: <span id="gyr-z" class="text-white">--</span></span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function fetchTelemetry() {
            try {
                const response = await fetch('/api/telemetry');
                const data = await response.json();
                
                // BME680
                const env = data.environment;
                if (env.temperature_c !== null) {
                    document.getElementById('temp').innerText = env.temperature_c + ' °C';
                    document.getElementById('hum').innerText = env.humidity_percent + ' %';
                    document.getElementById('pres').innerText = env.pressure_hpa + ' hPa';
                    document.getElementById('gas').innerText = (env.gas_ohms / 1000).toFixed(1) + ' kΩ';
                }

                // Kompas
                const comp = data.compass;
                const compStatus = document.getElementById('compass-status');
                if (comp.detected) {
                    compStatus.innerText = "Aktywny (I2C: 0x13)";
                    compStatus.className = "text-xs font-bold px-3 py-1 rounded bg-green-900 text-green-400 mb-4 uppercase";
                    
                    if (comp.heading_deg !== null) {
                        document.getElementById('heading-val').innerText = comp.heading_deg;
                        // Obracanie strzałki w CSS
                        document.getElementById('compass-needle').style.transform = `rotate(${comp.heading_deg}deg)`;
                    }
                }

                // LSM6DS3
                const mot = data.motion;
                if (mot.accel_m_s2 !== null) {
                    document.getElementById('acc-x').innerText = mot.accel_m_s2.x;
                    document.getElementById('acc-y').innerText = mot.accel_m_s2.y;
                    document.getElementById('acc-z').innerText = mot.accel_m_s2.z;
                    
                    document.getElementById('gyr-x').innerText = mot.gyro_rad_s.x;
                    document.getElementById('gyr-y').innerText = mot.gyro_rad_s.y;
                    document.getElementById('gyr-z').innerText = mot.gyro_rad_s.z;
                }
            } catch (error) {
                console.error("Błąd pobierania danych:", error);
            }
        }

        // Odświeżanie 2 razy na sekundę dla płynniejszego działania żyroskopu i kompasu
        setInterval(fetchTelemetry, 500);
        fetchTelemetry();
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_TEMPLATE

@app.get("/api/telemetry")
def get_telemetry():
    return sensors.get_all_data()

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
