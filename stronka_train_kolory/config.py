TRAINS_CONFIG = {
    "express": {"name": "Express", "mac": "9C:9A:C0:18:86:E1"},
    "cargo":   {"name": "Cargo",   "mac": "9C:9A:C0:1A:7A:AF"}
}

# Kody Lego: 3=Niebieski, 6=Zielony, 7=Żółty, 8=Pomarańczowy, 9=Czerwony, 10=Biały, 0=Brak
COLORS_CONFIG = {
    # --- STREFY BLOKADY LINIOWEJ ---
    3:  {"role": "zone", "zone_id": 1, "label": "NIEBIESKI", "ui_color": "blue",   "order": 1},
    6:  {"role": "zone", "zone_id": 2, "label": "ZIELONY",   "ui_color": "green",  "order": 2},
    7:  {"role": "zone", "zone_id": 3, "label": "ŻÓŁTY",     "ui_color": "yellow", "order": 3},
    10: {"role": "zone", "zone_id": 4, "label": "BIAŁY",     "ui_color": "slate",  "order": 4},
    
    # --- ZNAKI DROGOWE (AKCJE) ---
    # duration: Czas trwania akcji w sekundach
    # speed_limit: Do ilu % zwolnić pociąg
    9:  {"role": "action", "action": "stop", "label": "CZERWONY",  "ui_color": "red",    "duration": 15, "order": 10},
    8:  {"role": "action", "action": "slow", "label": "POMARAŃCZ", "ui_color": "orange", "duration": 10, "speed_limit": 40, "order": 11},
    
    # --- INNE ---
    0:  {"role": "none", "label": "BRAK", "ui_color": "gray", "order": 0}
}