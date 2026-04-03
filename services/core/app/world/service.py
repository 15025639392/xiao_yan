from datetime import datetime

from app.world.models import WorldState


class WorldStateService:
    def bootstrap(self) -> WorldState:
        hour = datetime.now().hour
        if hour < 6:
            value = "night"
        elif hour < 12:
            value = "morning"
        elif hour < 18:
            value = "afternoon"
        else:
            value = "evening"
        return WorldState(time_of_day=value)
