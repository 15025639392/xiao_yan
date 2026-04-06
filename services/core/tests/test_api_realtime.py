from fastapi.testclient import TestClient

from app.domain.models import BeingState, FocusMode, WakeMode
from app.goals.models import Goal, GoalStatus
from app.goals.repository import InMemoryGoalRepository
from app.main import app
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.memory.service import MemoryService
from app.persona.service import InMemoryPersonaRepository, PersonaService
from app.runtime import StateStore
from app.world.models import WorldState
from app.world.repository import InMemoryWorldRepository


def _install_runtime_for_realtime_test():
    memory_repository = InMemoryMemoryRepository()
    goal_repository = InMemoryGoalRepository()
    world_repository = InMemoryWorldRepository()
    persona_repository = InMemoryPersonaRepository()
    persona_service = PersonaService(repository=persona_repository)
    memory_service = MemoryService(
        repository=memory_repository,
        personality=persona_service.profile.personality,
    )
    state_store = StateStore(
        BeingState(mode=WakeMode.AWAKE, focus_mode=FocusMode.AUTONOMY),
        memory_repository=memory_repository,
    )

    app.state.memory_repository = memory_repository
    app.state.goal_repository = goal_repository
    app.state.world_repository = world_repository
    app.state.persona_service = persona_service
    app.state.memory_service = memory_service
    app.state.state_store = state_store

    return state_store, memory_repository, goal_repository, world_repository, persona_service


def test_realtime_socket_sends_initial_snapshot():
    state_store, memory_repository, goal_repository, world_repository, persona_service = _install_runtime_for_realtime_test()
    goal_repository.save_goal(
        Goal(
            title="整理今天的记忆",
            status=GoalStatus.ACTIVE,
            source="整理今天的记忆",
        )
    )
    world_repository.save_world_state(
        WorldState(
            time_of_day="night",
            energy="low",
            mood="calm",
            focus_tension="medium",
        )
    )
    memory_repository.save_event(MemoryEvent(kind="chat", role="user", content="你好"))
    memory_repository.save_event(MemoryEvent(kind="chat", role="assistant", content="你好，我在。"))
    memory_repository.save_event(MemoryEvent(kind="autobio", content="我刚整理过记忆。"))

    client = TestClient(app)
    with client.websocket_connect("/ws/app") as websocket:
        message = websocket.receive_json()

    assert message["type"] == "snapshot"
    assert message["payload"]["runtime"]["state"]["mode"] == "awake"
    assert message["payload"]["runtime"]["messages"][0]["content"] == "你好"
    assert message["payload"]["runtime"]["goals"][0]["title"] == "整理今天的记忆"
    assert message["payload"]["runtime"]["autobio"][0] == "我刚整理过记忆。"
    assert message["payload"]["memory"]["timeline"][0]["content"] == "我刚整理过记忆。"
    assert message["payload"]["persona"]["profile"]["name"] == persona_service.profile.name


def test_realtime_socket_pushes_runtime_memory_and_persona_updates():
    state_store, memory_repository, goal_repository, world_repository, persona_service = _install_runtime_for_realtime_test()
    world_repository.save_world_state(
        WorldState(
            time_of_day="morning",
            energy="medium",
            mood="engaged",
            focus_tension="low",
        )
    )

    client = TestClient(app)
    with client.websocket_connect("/ws/app") as websocket:
        assert websocket.receive_json()["type"] == "snapshot"

        state_store.set(
            BeingState(
                mode=WakeMode.AWAKE,
                focus_mode=FocusMode.MORNING_PLAN,
                current_thought="我想继续推进今天的事。",
                active_goal_ids=[],
            )
        )
        runtime_event = websocket.receive_json()

        memory_repository.save_event(MemoryEvent(kind="chat", role="user", content="新的记忆"))
        runtime_event_after_memory = websocket.receive_json()
        memory_event = websocket.receive_json()

        persona_service.update_personality(openness=81)
        persona_event = websocket.receive_json()

    assert runtime_event["type"] == "runtime_updated"
    assert runtime_event["payload"]["state"]["focus_mode"] == "morning_plan"
    assert runtime_event_after_memory["type"] == "runtime_updated"
    assert runtime_event_after_memory["payload"]["messages"][0]["content"] == "新的记忆"
    assert memory_event["type"] == "memory_updated"
    assert memory_event["payload"]["timeline"][0]["content"] == "新的记忆"
    assert persona_event["type"] == "persona_updated"
    assert persona_event["payload"]["profile"]["personality"]["openness"] == 81


def test_realtime_socket_pushes_chat_stream_events():
    _install_runtime_for_realtime_test()

    client = TestClient(app)
    with client.websocket_connect("/ws/app") as websocket:
        assert websocket.receive_json()["type"] == "snapshot"

        app.state.realtime_hub.publish_chat_started("assistant_1", response_id="resp_1")
        started_event = websocket.receive_json()

        app.state.realtime_hub.publish_chat_delta("assistant_1", "你")
        delta_event = websocket.receive_json()

        app.state.realtime_hub.publish_chat_completed("assistant_1", "resp_1", "你好")
        completed_event = websocket.receive_json()

    assert started_event["type"] == "chat_started"
    assert started_event["payload"]["assistant_message_id"] == "assistant_1"
    assert started_event["payload"]["response_id"] == "resp_1"
    assert started_event["payload"]["session_id"] == "assistant_1"
    assert started_event["payload"]["sequence"] == 1
    assert isinstance(started_event["payload"]["timestamp_ms"], int)

    assert delta_event["type"] == "chat_delta"
    assert delta_event["payload"]["assistant_message_id"] == "assistant_1"
    assert delta_event["payload"]["delta"] == "你"
    assert delta_event["payload"]["session_id"] == "assistant_1"
    assert delta_event["payload"]["sequence"] == 2
    assert isinstance(delta_event["payload"]["timestamp_ms"], int)

    assert completed_event["type"] == "chat_completed"
    assert completed_event["payload"]["assistant_message_id"] == "assistant_1"
    assert completed_event["payload"]["response_id"] == "resp_1"
    assert completed_event["payload"]["content"] == "你好"
    assert completed_event["payload"]["session_id"] == "assistant_1"
    assert completed_event["payload"]["sequence"] == 3
    assert isinstance(completed_event["payload"]["timestamp_ms"], int)
