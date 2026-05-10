from app.config import COLORS_CONFIG

class SystemLogger:
    def __init__(self, max_logs=10):
        self.logs = []
        self.max_logs = max_logs

    def log(self, message: str):
        print(message)
        self.logs.insert(0, message)
        if len(self.logs) > self.max_logs:
            self.logs.pop()

class ZoneDispatcher:
    def __init__(self, logger: SystemLogger):
        self.logger = logger
        self.zones = {v["zone_id"]: None for v in COLORS_CONFIG.values() if v.get("role") == "zone"}
        self.waiting_trains = {}

    def log(self, message: str):
        self.logger.log(message)

    async def free_zone_and_resume(self, zone_id: int):
        if zone_id in self.zones:
            self.zones[zone_id] = None
        
        for waiting_train, data in list(self.waiting_trains.items()):
            if data["zone"] == zone_id:
                saved_speed = data["speed"]
                self.log(f"[DISPATCHER] ZONE {zone_id} free! Resuming {waiting_train.name} ({saved_speed}%).")
                del self.waiting_trains[waiting_train]
                self.zones[zone_id] = waiting_train.name
                await waiting_train.send_speed(saved_speed)
                break 

    async def request_entry(self, train, zone_id: int):
        if zone_id not in self.zones: return
        if self.zones[zone_id] == train.name: return

        if self.zones[zone_id] is None:
            self.zones[zone_id] = train.name
            self.log(f"[DISPATCHER] {train.name} entered ZONE {zone_id}.")
            train.section = f"ZONE {zone_id}" 
            for z_id, occupant in self.zones.items():
                if occupant == train.name and z_id != zone_id:
                    await self.free_zone_and_resume(z_id)
        else:
            if train not in self.waiting_trains:
                occupant_name = self.zones[zone_id]
                self.log(f"[DISPATCHER] ZONE {zone_id} blocked by {occupant_name}. Stopping {train.name}.")
                self.waiting_trains[train] = {"zone": zone_id, "speed": train.speed}
                train.section = f"WAITING FOR ZONE {zone_id}"
                await train.stop()
