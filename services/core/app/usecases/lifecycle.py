from app.domain.models import BeingState, WakeMode


def wake_up() -> BeingState:
    return BeingState(
        mode=WakeMode.AWAKE,
        current_thought="我醒了，先整理一下现在的状态。",
    )


def go_to_sleep() -> BeingState:
    return BeingState(mode=WakeMode.SLEEPING)
