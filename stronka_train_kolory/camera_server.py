import subprocess
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
import socket

app = FastAPI()

def generate_frames():
    # Komenda uruchamiająca natywną obsługę Camera Module 3.
    # Używamy libcamera-vid (na nowym systemie Bookworm można zamienić na rpicam-vid).
    # Zwraca gotowy, skompresowany sprzętowo strumień MJPEG wprost do Pythona.
    cmd = [
        "libcamera-vid",
        "-t", "0",            # 0 = Nieskończony strumień
        "--codec", "mjpeg",   # Kodowanie MJPEG (lekkie dla Pi Zero W)
        "--width", "640",     # Niska rozdzielczość dla płynności
        "--height", "480",
        "--framerate", "15",  # 15 FPS nie "udusi" procesora Pi Zero W
        "--inline",           # Wymagane dla strumieniowania
        "-o", "-"             # Wyjście skierowane do konsoli (stdout)
    ]
    
    # Uruchamiamy proces w tle, bez wyświetlania zbędnych błędów
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    
    try:
        # Pętla czytająca surowy strumień i wydobywająca pojedyncze klatki JPEG
        chunk_size = 4096
        stream = b''
        
        while True:
            data = process.stdout.read(chunk_size)
            if not data:
                break
            
            stream += data
            
            # Magia JPEG: Każdy plik obrazu zaczyna się od bitów FF D8, a kończy FF D9
            start = stream.find(b'\xff\xd8')
            end = stream.find(b'\xff\xd9')
            
            if start != -1 and end != -1:
                # Wycinamy pełną klatkę
                jpg = stream[start:end+2]
                # Czyścimy bufor o przetworzoną klatkę
                stream = stream[end+2:]
                
                # Zwracamy klatkę jako fragment wieloczęściowej odpowiedzi HTTP (Multipart)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')
                       
    except GeneratorExit:
        # Bezpieczne zamknięcie kamery, gdy zamkniesz kartę w przeglądarce
        process.terminate()

@app.get("/video")
def video_feed():
    """Endpoint udostępniający żywy obraz wideo."""
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/", response_class=HTMLResponse)
def index():
    """Tymczasowy podgląd kamery w przeglądarce (opcjonalny, do testów)."""
    return """
    <!DOCTYPE html>
    <html lang="pl">
    <head><title>Kamera Pokładowa</title></head>
    <body style="background: #111; color: white; display: flex; flex-direction: column; align-items: center; margin-top: 50px; font-family: sans-serif;">
        <h2>Podgląd Na Żywo - Camera Module 3</h2>
        <img src="/video" style="border: 2px solid #555; border-radius: 10px; width: 640px; max-width: 100%;" />
    </body>
    </html>
    """
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
    print("="*55 + "\n")
    print(f"Uruchamianie serwera kamery na http://{local_ip}:8001")
    print("="*55 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8001, access_log=False)
    # Uruchamiamy serwer wideo na porcie 8001, by nie gryzł się z głównym serwerem (8000)



'''
TODO Wkleić do index.html jako widok na naszej stronie
<div class="mt-8 bg-gray-900 p-4 rounded-xl border border-gray-700 shadow-inner flex flex-col items-center">
    <h3 class="text-gray-500 text-xs font-bold mb-3 uppercase tracking-widest flex items-center w-full">
        <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse mr-2"></span> Kamera Pokładowa
    </h3>
    <img id="train-cam" src="http://127.0.0.1:8001/video" class="rounded border-2 border-gray-600 w-full max-w-md shadow-lg" alt="Ładowanie kamery..." />
</div>
'''