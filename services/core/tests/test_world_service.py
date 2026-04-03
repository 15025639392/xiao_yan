from app.world.service import WorldStateService


def test_world_state_bootstraps_daily_rhythm():
    service = WorldStateService()
    state = service.bootstrap()
    assert state.time_of_day in {"morning", "afternoon", "evening", "night"}
