# Plik: sensor_server.py (NA RASPBERRY PI ZERO)
from socket import socket
import time
import board
from fastapi import FastAPI
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
    print("Uruchamiam serwer czujników na porcie 8002...")
    local_ip = get_local_ip()
    print("\n" + "="*55)
    print(f" Otwórz panel sterowania: http://{local_ip}:8002")
    print("="*55 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8002, access_log=False)