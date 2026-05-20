import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

LOCAL_IP = get_local_ip()

# Train configuration
TRAINS_CONFIG = {
    "express": {"name": "Express", "mac": "9C:9A:C0:18:86:E1", "rasp_url": "http://192.168.0.72:8001"},
    "cargo":   {"name": "Cargo",   "mac": "9C:9A:C0:1A:7A:AF", "rasp_url": f"http://{LOCAL_IP}:8002"}
}

# Block configurations
COLORS_CONFIG = {
    # --- LINE BLOCK ZONES ---
    "S1":  {"role": "zone", "zone_id": 1, "label": "BLUE", "ui_color": "blue", "order": 1,
         "rgb_range": {"r": (10, 40), "g": (50, 80), "b": (100, 150)}},  
         
    "S2":  {"role": "zone", "zone_id": 2, "label": "GREEN", "ui_color": "green", "order": 2,
         "rgb_range": {"r": (0, 80), "g": (70, 100), "b": (40, 70)}},
         
    "S3":  {"role": "zone", "zone_id": 3, "label": "ORANGE", "ui_color": "orange", "order": 3,
         "rgb_range": {"r": (70, 130), "g": (30, 60), "b": (0, 40)}},
         
    "S4": {"role": "zone", "zone_id": 4, "label": "WHITE", "ui_color": "slate", "order": 4,
         "rgb_range": {"r": (210, 255), "g": (210, 255), "b": (210, 255)}},
    
    # --- ACTIONS ---
    "ST":  {"role": "action", "action": "stop", "label": "RED (STOP)",  "ui_color": "red", "duration": 15, "order": 10,
         "rgb_range": {"r": (150, 180), "g": (0, 40), "b": (30, 65)}},

    #"SL":  {"role": "action", "action": "slow", "label": "BROWN (LIMIT)", "ui_color": "orange", "duration": 5, "speed_limit": 40, "order": 11,
    #     "rgb_range": {"r": (30, 70), "g": (20, 50), "b": (20, 50)}},
}

