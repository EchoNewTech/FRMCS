import socket
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import board
import uvicorn

# Próba importu bibliotek z obsługą błędów, 
# aby brak jednej nie blokował działania całości.
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

        # --- Inicjalizacja BME680 (Temperatura, Wilgotność, Ciśnienie, Gaz) ---
        self.bme = None
        if self.i2c and adafruit_bme680:
            try:
                # Adres standardowy to 0x76 lub 0x77
                self.bme = adafruit_bme680.Adafruit_BME680_I2C(self.i2c)
                self.bme.sea_level_pressure = 1013.25 # Do obliczania wysokości
                print("[SENSORY] BME680 podłączony poprawnie.")
            except Exception as e:
                print(f"[SENSORY] Nie znaleziono BME680 na I2C: {e}")

        # --- Inicjalizacja LSM6DS3 (Akcelerometr, Żyroskop) ---
        self.lsm = None
        if self.i2c and LSM6DS3:
            try:
                # Adres standardowy to 0x6A lub 0x6B
                self.lsm = LSM6DS3(self.i2c)
                print("[SENSORY] LSM6DS3 podłączony poprawnie.")
            except Exception as e:
                print(f"[SENSORY] Nie znaleziono LSM6DS3 na I2C: {e}")

        # --- Inicjalizacja Kompasu Grove V2.0 (BMM150) ---
        self.compass_detected = False
        try:
            # Skrypt skanuje urządzenia I2C, adres BMM150 to zazwyczaj 0x13
            import smbus2
            bus = smbus2.SMBus(1)
            bus.read_byte(0x13)
            self.compass_detected = True
            print("[SENSORY] Kompas V2 (0x13) wykryty.")
        except Exception:
            pass

    def get_all_data(self):
        """Zwraca słownik z kompletem dostępnych pomiarów."""
        data = {
            "environment": {"temperature_c": None, "humidity_percent": None, "pressure_hpa": None, "gas_ohms": None},
            "motion": {"accel_m_s2": None, "gyro_rad_s": None},
            "compass": {"detected": self.compass_detected, "heading": None}
        }

        # Odczyt BME680
        if self.bme:
            try:
                data["environment"]["temperature_c"] = round(self.bme.temperature, 2)
                data["environment"]["humidity_percent"] = round(self.bme.humidity, 2)
                data["environment"]["pressure_hpa"] = round(self.bme.pressure, 2)
                data["environment"]["gas_ohms"] = round(self.bme.gas, 2)
            except Exception as e:
                pass

        # Odczyt LSM6DS3
        if self.lsm:
            try:
                accel_x, accel_y, accel_z = self.lsm.acceleration
                gyro_x, gyro_y, gyro_z = self.lsm.gyro
                data["motion"]["accel_m_s2"] = {"x": round(accel_x, 2), "y": round(accel_y, 2), "z": round(accel_z, 2)}
                data["motion"]["gyro_rad_s"] = {"x": round(gyro_x, 2), "y": round(gyro_y, 2), "z": round(gyro_z, 2)}
            except Exception as e:
                pass

        return data


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
    <p class="text-gray-400 text-sm mb-8">Odświeżanie na żywo co 1 sekundę</p>

    <div class="w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-6">
        
        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg">
            <h2 class="text-xl font-bold text-gray-300 border-b border-gray-600 pb-2 mb-4">Środowisko (BME680)</h2>
            <div class="grid grid-cols-2 gap-4 text-center">
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

        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg">
            <h2 class="text-xl font-bold text-gray-300 border-b border-gray-600 pb-2 mb-4">Ruch (LSM6DS3)</h2>
            <div class="space-y-4">
                <div class="bg-gray-900 p-3 rounded">
                    <span class="text-xs text-gray-500 uppercase block mb-1">Akcelerometr (m/s²)</span>
                    <div class="flex justify-between font-mono text-sm">
                        <span class="text-red-400">X: <span id="acc-x" class="text-white">--</span></span>
                        <span class="text-green-400">Y: <span id="acc-y" class="text-white">--</span></span>
                        <span class="text-blue-400">Z: <span id="acc-z" class="text-white">--</span></span>
                    </div>
                </div>
                <div class="bg-gray-900 p-3 rounded">
                    <span class="text-xs text-gray-500 uppercase block mb-1">Żyroskop (rad/s)</span>
                    <div class="flex justify-between font-mono text-sm">
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
                
                const env = data.environment;
                if (env.temperature_c !== null) {
                    document.getElementById('temp').innerText = env.temperature_c + ' °C';
                    document.getElementById('hum').innerText = env.humidity_percent + ' %';
                    document.getElementById('pres').innerText = env.pressure_hpa + ' hPa';
                    document.getElementById('gas').innerText = (env.gas_ohms / 1000).toFixed(1) + ' kΩ';
                }

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

        // Odświeżaj dane co 1000 milisekund (1 sekunda)
        setInterval(fetchTelemetry, 1000);
        fetchTelemetry(); // Pierwsze wywołanie od razu
    </script>
</body>
</html>
"""

# Zwracanie interfejsu graficznego w przeglądarce
@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_TEMPLATE

# Główne API zwracające dane dla Raspberry Pi 4 (lub skryptu JS wyżej)
@app.get("/api/telemetry")
def get_telemetry():
    """Zwraca aktualne odczyty z czujników I2C jako JSON"""
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
