from app.config import COLORS_CONFIG

class SystemLogger:
    def __init__(self, max_logs=5):
        self.logs = []
        self.max_logs = max_logs

    def log(self, message: str):
        print(message)
        self.logs.insert(0, message)
        if len(self.logs) > self.max_logs:
            self.logs.pop()

def get_zone_label(zone_id: int) -> str:
    for code, cfg in COLORS_CONFIG.items():
        if cfg.get("role") == "zone" and cfg.get("zone_id") == zone_id:
            return cfg.get("label", f"ZONE {zone_id}")
    return str(zone_id)

class ZoneDispatcher:
    def __init__(self, logger: SystemLogger):
        self.logger = logger
        # Auto-build zones based on config.py
        self.zones = {v["zone_id"]: None for v in COLORS_CONFIG.values() if v.get("role") == "zone"}
        self.waiting_trains = {}

    def log(self, message: str):
        self.logger.log(message)

    async def free_zone_and_resume(self, zone_id: int):
        """Frees the zone and resumes the first waiting train with its original captured speed."""
        if zone_id in self.zones:
            self.zones[zone_id] = None
        
        for waiting_train, data in list(self.waiting_trains.items()):
            if data["zone"] == zone_id:
                # Retrieve the exact speed the train had before being blocked
                saved_speed = data["speed"]
                
                self.log(f"[DISPATCHER] ZONE {zone_id} free! Resuming {waiting_train.name} ({saved_speed}%).")
                
                del self.waiting_trains[waiting_train]
                self.zones[zone_id] = waiting_train
                
                # Update UI Status (Only Zones!)
                label = get_zone_label(zone_id)
                waiting_train.section = f"ZONE {zone_id} ({label})"
                
                # Send the original speed back to the train
                await waiting_train.send_speed(saved_speed)
                
                # Cascade free if this train was occupying previous zones
                for z in list(self.zones.keys()):
                    if self.zones[z] == waiting_train and z != zone_id:
                        await self.free_zone_and_resume(z)
                break 

    async def request_entry(self, train, zone_id: int):
        """Handles zone entry requests. Blocks and saves speed if occupied."""
        if zone_id not in self.zones:
            self.zones[zone_id] = None

        label = get_zone_label(zone_id)

        if self.zones[zone_id] == train:
            # Ensure UI doesn't hang on "WAITING" if it's already inside
            if "WAITING" not in getattr(train, "section", ""):
                train.section = f"ZONE {zone_id} ({label})"
            return

        if self.zones[zone_id] is None:
            old_zone = None
            for zid, occupant in self.zones.items():
                if occupant == train:
                    old_zone = zid
                    break
            
            self.zones[zone_id] = train
            self.log(f"[DISPATCHER] {train.name} entered ZONE {zone_id}.")
            train.section = f"ZONE {zone_id} ({label})"

            if old_zone is not None:
                await self.free_zone_and_resume(old_zone)
        else:
            if train not in self.waiting_trains:
                blocker = self.zones[zone_id]
                blocker_name = blocker.name if hasattr(blocker, 'name') else "Another train"
                self.log(f"[DISPATCHER] ZONE {zone_id} occupied by {blocker_name}. Stopping {train.name}")
                
                # CAPTURE EXACT CURRENT SPEED before stopping
                self.waiting_trains[train] = {"zone": zone_id, "speed": train.speed}
                train.section = f"WAITING FOR ZONE {zone_id} ({label})"
                await train.send_speed(0)
