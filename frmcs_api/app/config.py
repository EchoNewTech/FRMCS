import socket

# Train configuration
TRAINS_CONFIG = {
    "express": {"name": "Express", "mac": "9C:9A:C0:18:86:E1", "rasp_url": "http://192.168.1.172:8000"},
    "cargo":   {"name": "Cargo",   "mac": "9C:9A:C0:1A:7A:AF", "rasp_url": "http://192.168.1.117:8000"}
}

# Block configurations
COLORS_CONFIG = {
    # --- LINE BLOCK ZONES ---
    "S1":  {"role": "zone", "zone_id": 1, "label": "BLUE", "ui_color": "blue", "order": 1,
         "rgb_range": {"r": (20, 40), "g": (50, 80), "b": (110, 140)}},  
         
    "S2":  {"role": "zone", "zone_id": 2, "label": "GREEN", "ui_color": "green", "order": 2,
          "rgb_range": {"r": (30, 50), "g": (60, 90), "b": (40, 70)}},
         
    "S3":  {"role": "zone", "zone_id": 3, "label": "RED", "ui_color": "red", "order": 3,
         "rgb_range": {"r": (130, 160), "g": (30, 50), "b": (45, 65)}},
         
    "S4": {"role": "zone", "zone_id": 4, "label": "WHITE", "ui_color": "slate", "order": 4,
         "rgb_range": {"r": (210, 255), "g": (210, 255), "b": (210, 255)}},
    
    # --- ACTIONS ---
    "ST":  {"role": "action", "action": "stop", "label": "YELLOW (STOP)",  "ui_color": "yellow", "duration": 15, "order": 10,
         "rgb_range": {"r": (200, 255), "g": (150, 180), "b": (100, 130)}},

     0: {"role": "none", "label": "NONE", "ui_color": "gray", "order": 0}

}

