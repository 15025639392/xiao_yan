from app.domain.models import WakeMode
from app.runtime import StateStore


def test_state_store_defaults_to_sleeping():
    store = StateStore()

    assert store.get().mode == WakeMode.SLEEPING


def test_state_store_persists_latest_state():
    store = StateStore()

    updated = store.wake()
    assert updated.mode == WakeMode.AWAKE

    sleeping = store.sleep()
    assert sleeping.mode == WakeMode.SLEEPING
    assert store.get().mode == WakeMode.SLEEPING
