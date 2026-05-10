TRAINS_CONFIG = {
    "express": {"name": "Express", "mac": "9C:9A:C0:18:86:E1"},
    "cargo":   {"name": "Cargo",   "mac": "9C:9A:C0:1A:7A:AF"}
}

COLORS_CONFIG = {
    "S1": {
        "role": "zone", "zone_id": 1, "label": "BLUE ZONE", "ui_color": "blue",
        "rgb_range": {"r": (10, 120), "g": (40, 130), "b": (60, 160)}
    },
    "S2": {
        "role": "zone", "zone_id": 2, "label": "GREEN ZONE", "ui_color": "green",
        "rgb_range": {"r": (10, 120), "g": (50, 120), "b": (40, 110)}
    },
    "S3": {
        "role": "zone", "zone_id": 3, "label": "YELLOW ZONE", "ui_color": "yellow",
        "rgb_range": {"r": (400, 1024), "g": (400, 1024), "b": (0, 300)}
    },
    "S4": {
        "role": "zone", "zone_id": 4, "label": "WHITE ZONE", "ui_color": "slate",
        "rgb_range": {"r": (800, 1024), "g": (800, 1024), "b": (800, 1024)}
    },
    "ST": {
        "role": "action", "action": "stop", "label": "RED (STOP)", "ui_color": "red", "duration": 15,
        "rgb_range": {"r": (500, 1024), "g": (0, 350), "b": (0, 400)}
    },
    "SL": {
        "role": "action", "action": "slow", "label": "BROWN (LIMIT)", "ui_color": "orange", "duration": 10, "speed_limit": 40,
        "rgb_range": {"r": (300, 600), "g": (100, 400), "b": (0, 250)}
    }
}
