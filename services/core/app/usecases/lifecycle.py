from app.domain.models import BeingState, WakeMode


def wake_up(recent_autobio: str | None = None) -> BeingState:
    thought = "我醒了，先整理一下现在的状态。"
    if recent_autobio:
        thought = f"我醒了，先回想一下自己最近的变化：{recent_autobio}"

    return BeingState(
        mode=WakeMode.AWAKE,
        current_thought=thought,
    )


def go_to_sleep() -> BeingState:
    return BeingState(mode=WakeMode.SLEEPING)
