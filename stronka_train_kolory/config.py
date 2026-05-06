TRAINS_CONFIG = {
    "express": {"name": "Express", "mac": "9C:9A:C0:18:86:E1"},
    "cargo":   {"name": "Cargo",   "mac": "9C:9A:C0:1A:7A:AF"}
}

# Kody Lego: 3=Niebieski, 6=Zielony, 7=Żółty, 8=Pomarańczowy, 9=Czerwony, 10=Biały, 0=Brak
# Nowe kody: 11=Czarny, 12=Brązowy, 13=Lazurowy, 14=Turkusowy, 15=Jasny Pomarańcz
COLORS_CONFIG = {
    # --- STREFY BLOKADY LINIOWEJ ---
    "S1":  {"role": "zone", "zone_id": 1, "label": "NIEBIESKI", "ui_color": "blue", "order": 1,
         "rgb_range": {"r": (10, 40), "g": (50, 80), "b": (100, 150)}},  
         
    "S2":  {"role": "zone", "zone_id": 2, "label": "ZIELONY", "ui_color": "green", "order": 2,
         "rgb_range": {"r": (0, 80), "g": (70, 100), "b": (40, 70)}},
         
    "S3":  {"role": "zone", "zone_id": 3, "label": "POMARAŃCZOWY", "ui_color": "orange", "order": 3,
         "rgb_range": {"r": (70, 130), "g": (30, 60), "b": (0, 40)}},
         
    "S4": {"role": "zone", "zone_id": 4, "label": "BIAŁY", "ui_color": "slate", "order": 4,
         "rgb_range": {"r": (210, 255), "g": (210, 255), "b": (210, 255)}},
    
    # --- ZNAKI DROGOWE (AKCJE) ---
    "ST":  {"role": "action", "action": "stop", "label": "CZERWONY",  "ui_color": "red", "duration": 15, "order": 10,
         "rgb_range": {"r": (150, 180), "g": (0, 40), "b": (30, 65)}},

    "SL":  {"role": "action", "action": "slow", "label": "BRĄZOWY", "ui_color": "orange", "duration": 5, "speed_limit": 40, "order": 11,
         # PRZYWRÓCONO! G kończy się na 125.
         "rgb_range": {"r": (30, 70), "g": (20, 50), "b": (20, 50)}},
}