from config import COLORS_CONFIG

class SystemLogger:
    def __init__(self, max_logs=5):
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
        # Automatyczne budowanie liczby stref na podstawie config.py
        self.zones = {v["zone_id"]: None for v in COLORS_CONFIG.values() if v.get("role") == "zone"}
        self.waiting_trains = {}

    def log(self, message: str):
        self.logger.log(message)

    async def free_zone_and_resume(self, zone_id: int):
        """Zwalnia strefę i wznawia ruch pierwszego pociągu z kolejki oczekujących, który czekał na tę strefę."""
        if zone_id in self.zones:
            self.zones[zone_id] = None
        
        for waiting_train, data in list(self.waiting_trains.items()):
            if data["zone"] == zone_id:
                saved_speed = data["speed"]
                self.log(f"[DYSPOZYTOR] STREFA {zone_id} wolna! Wznawiam {waiting_train.name} ({saved_speed}%).")
                
                del self.waiting_trains[waiting_train]
                self.zones[zone_id] = waiting_train
                await waiting_train.set_speed(saved_speed)
                
                for z in list(self.zones.keys()):
                    if self.zones[z] == waiting_train and z != zone_id:
                        await self.free_zone_and_resume(z)
                break 

    async def request_entry(self, train, zone_id: int):
        """Obsługuje prośbę pociągu o wjazd do strefy. Jeśli strefa jest wolna, przydziela ją pociągowi. Jeśli zajęta, zatrzymuje pociąg i dodaje do kolejki oczekujących."""
        if zone_id not in self.zones:
            self.zones[zone_id] = None

        if self.zones[zone_id] == train:
            return

        if self.zones[zone_id] is None:
            self.zones[zone_id] = train
            self.log(f"[DYSPOZYTOR] {train.name} wjechał do STREFY {zone_id}.")

            for z_id in list(self.zones.keys()):
                if self.zones[z_id] == train and z_id != zone_id:
                    await self.free_zone_and_resume(z_id)
        else:
            if train not in self.waiting_trains:
                blokujacy_train = self.zones[zone_id]
                self.log(f"[DYSPOZYTOR] STREFA {zone_id} zajęta przez {blokujacy_train.name}. Zatrzymuję {train.name}")
                self.waiting_trains[train] = {"zone": zone_id, "speed": train.speed}
                await train.set_speed(0)