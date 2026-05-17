import socket

# Funkcja pobierająca aktualne IP Twojego komputera/serwera w sieci lokalnej
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# Automatyczne pobranie IP do zmiennej
LOCAL_IP = get_local_ip()

TRAINS_CONFIG = {
    "express": {
        "name": "Express", 
        "mac": "9C:9A:C0:18:86:E1",
        "rasp_url": "http://192.168.0.72:8001"
    },
    "cargo": {
        "name": "Cargo",   
        "mac": "9C:9A:C0:1A:7A:AF",
        "rasp_url": f"http://{LOCAL_IP}:8002"
    }
}

# Kody Lego: 3=Niebieski, 6=Zielony, 7=Żółty, 8=Pomarańczowy, 9=Czerwony, 10=Biały, 0=Brak
# Nowe kody: 11=Czarny, 12=Brązowy, 13=Lazurowy, 14=Turkusowy, 15=Jasny Pomarańcz
COLORS_CONFIG = {
    # STREFY
    "S1":  {"role": "zone", "zone_id": 1, "label": "NIEBIESKI", "ui_color": "blue", "order": 1,
         "rgb_center": {"r": 40, "g": 75, "b": 160}, "distance_threshold": 55},  
         
    "S2":  {"role": "zone", "zone_id": 2, "label": "ZIELONY", "ui_color": "green", "order": 2,
         "rgb_center": {"r": 35, "g": 100, "b": 40}, "distance_threshold": 55},
         
    "S3":  {"role": "zone", "zone_id": 3, "label": "POMARAŃCZOWY", "ui_color": "orange", "order": 3,
         "rgb_center": {"r": 210, "g": 95, "b": 30}, "distance_threshold": 50},
         
    "S4": {"role": "zone", "zone_id": 4, "label": "BIAŁY", "ui_color": "slate", "order": 4,
         "rgb_center": {"r": 240, "g": 240, "b": 240}, "distance_threshold": 35},
    
    # AKCJE
    "ST":  {"role": "action", "action": "stop", "label": "CZERWONY",  "ui_color": "red", "duration": 15, "order": 10,
         "rgb_center": {"r": 180, "g": 30, "b": 50}, "distance_threshold": 40},

    "SL":  {"role": "action", "action": "slow", "label": "BRĄZOWY", "ui_color": "orange", "duration": 5, "speed_limit": 40, "order": 11,
         "rgb_center": {"r": 110, "g": 70, "b": 40}, "distance_threshold": 45},
}