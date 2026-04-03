# 数字人 MVP 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 从空仓库搭建一个“人格优先”的高自治数字人 MVP，支持睡眠/苏醒、长期记忆、主动循环、GPT 调用，以及受控电脑助手能力。

**Architecture:** 使用 `Tauri + React + TypeScript` 构建桌面交互壳，使用 `Python + FastAPI` 构建人格与执行内核。后端按“人格层、记忆层、执行层、调度层、工具层”拆分，前端只负责状态呈现、对话和权限确认。

**Tech Stack:** Tauri, React, TypeScript, Vite, Python 3.12, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, pgvector, APScheduler, pytest

---

### Task 1: 初始化仓库骨架

**Files:**
- Create: `README.md`
- Create: `apps/desktop/package.json`
- Create: `apps/desktop/src/main.tsx`
- Create: `apps/desktop/src/App.tsx`
- Create: `services/core/pyproject.toml`
- Create: `services/core/app/main.py`
- Create: `.gitignore`

**Step 1: 写失败测试**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_healthcheck_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`

**Step 3: 写最小实现**

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_health.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add README.md apps/desktop services/core .gitignore
git commit -m "feat: 初始化数字人项目骨架"
```

### Task 2: 建立核心领域模型

**Files:**
- Create: `services/core/app/domain/models.py`
- Create: `services/core/tests/test_domain_models.py`

**Step 1: 写失败测试**

```python
from app.domain.models import BeingState, WakeMode


def test_default_being_state_is_sleeping():
    state = BeingState.default()
    assert state.mode == WakeMode.SLEEPING
    assert state.current_thought is None
    assert state.active_goal_ids == []
```

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_domain_models.py -v`
Expected: FAIL with `ImportError` for `BeingState`

**Step 3: 写最小实现**

```python
from enum import Enum

from pydantic import BaseModel, Field


class WakeMode(str, Enum):
    AWAKE = "awake"
    SLEEPING = "sleeping"


class BeingState(BaseModel):
    mode: WakeMode
    current_thought: str | None = None
    active_goal_ids: list[str] = Field(default_factory=list)

    @classmethod
    def default(cls) -> "BeingState":
        return cls(mode=WakeMode.SLEEPING)
```

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_domain_models.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/domain/models.py services/core/tests/test_domain_models.py
git commit -m "feat: 添加数字人核心领域模型"
```

### Task 3: 实现人格配置与系统提示构造器

**Files:**
- Create: `services/core/app/persona/config.py`
- Create: `services/core/app/persona/prompt_builder.py`
- Create: `services/core/tests/test_prompt_builder.py`

**Step 1: 写失败测试**

```python
from app.persona.config import PersonaConfig
from app.persona.prompt_builder import build_persona_prompt


def test_prompt_contains_identity_and_values():
    config = PersonaConfig(
        name="Aira",
        identity="持续存在的数字人",
        values=["诚实", "主动", "有边界"],
    )
    prompt = build_persona_prompt(config)
    assert "Aira" in prompt
    assert "持续存在的数字人" in prompt
    assert "诚实" in prompt
```

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_prompt_builder.py -v`
Expected: FAIL with missing persona modules

**Step 3: 写最小实现**

```python
from pydantic import BaseModel, Field


class PersonaConfig(BaseModel):
    name: str
    identity: str
    values: list[str] = Field(default_factory=list)
```

```python
from app.persona.config import PersonaConfig


def build_persona_prompt(config: PersonaConfig) -> str:
    values = "、".join(config.values)
    return (
        f"你是 {config.name}。\n"
        f"身份：{config.identity}\n"
        f"核心价值：{values}\n"
        "你是持续存在的人格体，而不是一次性问答助手。"
    )
```

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_prompt_builder.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/persona services/core/tests/test_prompt_builder.py
git commit -m "feat: 添加人格配置与提示构造器"
```

### Task 4: 封装 GPT 模型网关

**Files:**
- Create: `services/core/app/llm/gateway.py`
- Create: `services/core/app/llm/schemas.py`
- Create: `services/core/tests/test_gateway.py`

**Step 1: 写失败测试**

```python
from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage


def test_gateway_normalizes_messages():
    gateway = ChatGateway(api_key="test-key", model="gpt-5.4")
    payload = gateway.build_payload([ChatMessage(role="user", content="hi")])
    assert payload["model"] == "gpt-5.4"
    assert payload["messages"][0]["content"] == "hi"
```

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_gateway.py -v`
Expected: FAIL with missing llm modules

**Step 3: 写最小实现**

```python
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str
```

```python
from app.llm.schemas import ChatMessage


class ChatGateway:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def build_payload(self, messages: list[ChatMessage]) -> dict:
        return {
            "model": self.model,
            "messages": [message.model_dump() for message in messages],
        }
```

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_gateway.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/llm services/core/tests/test_gateway.py
git commit -m "feat: 封装模型调用网关"
```

### Task 5: 建立记忆存储接口

**Files:**
- Create: `services/core/app/memory/models.py`
- Create: `services/core/app/memory/repository.py`
- Create: `services/core/tests/test_memory_repository.py`

**Step 1: 写失败测试**

```python
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository


def test_repository_saves_event_and_returns_recent_items():
    repo = InMemoryMemoryRepository()
    event = MemoryEvent(kind="episode", content="她在醒来后主动问候用户")
    repo.save_event(event)
    recent = repo.list_recent(limit=5)
    assert recent[0].content == "她在醒来后主动问候用户"
```

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_memory_repository.py -v`
Expected: FAIL with missing memory modules

**Step 3: 写最小实现**

```python
from pydantic import BaseModel


class MemoryEvent(BaseModel):
    kind: str
    content: str
```

```python
from app.memory.models import MemoryEvent


class InMemoryMemoryRepository:
    def __init__(self) -> None:
        self._events: list[MemoryEvent] = []

    def save_event(self, event: MemoryEvent) -> None:
        self._events.append(event)

    def list_recent(self, limit: int) -> list[MemoryEvent]:
        return list(reversed(self._events[-limit:]))
```

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_memory_repository.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/memory services/core/tests/test_memory_repository.py
git commit -m "feat: 添加记忆存储接口"
```

### Task 6: 实现睡眠与苏醒用例

**Files:**
- Create: `services/core/app/usecases/lifecycle.py`
- Create: `services/core/tests/test_lifecycle.py`

**Step 1: 写失败测试**

```python
from app.domain.models import WakeMode
from app.usecases.lifecycle import wake_up, go_to_sleep


def test_wake_up_transitions_state_and_generates_brief():
    state = wake_up()
    assert state.mode == WakeMode.AWAKE
    assert state.current_thought is not None


def test_go_to_sleep_transitions_state():
    state = go_to_sleep()
    assert state.mode == WakeMode.SLEEPING
```

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_lifecycle.py -v`
Expected: FAIL with missing lifecycle usecases

**Step 3: 写最小实现**

```python
from app.domain.models import BeingState, WakeMode


def wake_up() -> BeingState:
    return BeingState(mode=WakeMode.AWAKE, current_thought="我醒了，先整理一下现在的状态。")


def go_to_sleep() -> BeingState:
    return BeingState(mode=WakeMode.SLEEPING)
```

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_lifecycle.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/usecases/lifecycle.py services/core/tests/test_lifecycle.py
git commit -m "feat: 添加睡眠与苏醒用例"
```

### Task 7: 实现主动思考循环

**Files:**
- Create: `services/core/app/agent/autonomy.py`
- Create: `services/core/tests/test_autonomy.py`

**Step 1: 写失败测试**

```python
from app.agent.autonomy import choose_next_action
from app.domain.models import BeingState, WakeMode


def test_awake_state_without_goal_prefers_reflection():
    state = BeingState(mode=WakeMode.AWAKE)
    action = choose_next_action(state=state, pending_goals=[], recent_events=[])
    assert action.kind == "reflect"
```

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_autonomy.py -v`
Expected: FAIL with missing autonomy module

**Step 3: 写最小实现**

```python
from pydantic import BaseModel

from app.domain.models import BeingState


class NextAction(BaseModel):
    kind: str
    reason: str


def choose_next_action(
    state: BeingState,
    pending_goals: list[str],
    recent_events: list[str],
) -> NextAction:
    if pending_goals:
        return NextAction(kind="act", reason="存在未完成目标")
    return NextAction(kind="reflect", reason="当前没有待执行目标")
```

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_autonomy.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/agent/autonomy.py services/core/tests/test_autonomy.py
git commit -m "feat: 添加主动决策循环"
```

### Task 8: 实现受控电脑助手沙箱

**Files:**
- Create: `services/core/app/tools/sandbox.py`
- Create: `services/core/tests/test_sandbox.py`

**Step 1: 写失败测试**

```python
import pytest

from app.tools.sandbox import CommandSandbox


def test_sandbox_allows_whitelisted_command():
    sandbox = CommandSandbox(allowed_commands={"pwd"})
    result = sandbox.validate("pwd")
    assert result == "pwd"


def test_sandbox_blocks_non_whitelisted_command():
    sandbox = CommandSandbox(allowed_commands={"pwd"})
    with pytest.raises(PermissionError):
        sandbox.validate("rm -rf /")
```

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_sandbox.py -v`
Expected: FAIL with missing sandbox module

**Step 3: 写最小实现**

```python
class CommandSandbox:
    def __init__(self, allowed_commands: set[str]) -> None:
        self.allowed_commands = allowed_commands

    def validate(self, command: str) -> str:
        executable = command.strip().split()[0]
        if executable not in self.allowed_commands:
            raise PermissionError(f"command not allowed: {executable}")
        return command
```

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_sandbox.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/tools/sandbox.py services/core/tests/test_sandbox.py
git commit -m "feat: 添加电脑助手命令沙箱"
```

### Task 9: 暴露生命周期与对话 API

**Files:**
- Modify: `services/core/app/main.py`
- Create: `services/core/tests/test_api_lifecycle.py`

**Step 1: 写失败测试**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_post_wake_returns_awake_state():
    client = TestClient(app)
    response = client.post("/lifecycle/wake")
    assert response.status_code == 200
    assert response.json()["mode"] == "awake"
```

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_api_lifecycle.py -v`
Expected: FAIL with `404 Not Found`

**Step 3: 写最小实现**

```python
from fastapi import FastAPI

from app.usecases.lifecycle import go_to_sleep, wake_up

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/lifecycle/wake")
def wake() -> dict:
    return wake_up().model_dump()


@app.post("/lifecycle/sleep")
def sleep() -> dict:
    return go_to_sleep().model_dump()
```

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_api_lifecycle.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/main.py services/core/tests/test_api_lifecycle.py
git commit -m "feat: 暴露数字人生命周期接口"
```

### Task 10: 搭建桌面端最小交互壳

**Files:**
- Modify: `apps/desktop/src/App.tsx`
- Create: `apps/desktop/src/components/StatusPanel.tsx`
- Create: `apps/desktop/src/components/ChatPanel.tsx`
- Create: `apps/desktop/src/lib/api.ts`
- Create: `apps/desktop/src/App.test.tsx`

**Step 1: 写失败测试**

```tsx
import { render, screen } from "@testing-library/react";
import App from "./App";


test("renders wake and sleep controls", () => {
  render(<App />);
  expect(screen.getByText("Wake")).toBeInTheDocument();
  expect(screen.getByText("Sleep")).toBeInTheDocument();
});
```

**Step 2: 运行测试并确认失败**

Run: `cd apps/desktop && npm test -- App.test.tsx`
Expected: FAIL with missing App implementation

**Step 3: 写最小实现**

```tsx
export default function App() {
  return (
    <main>
      <h1>Digital Being</h1>
      <button>Wake</button>
      <button>Sleep</button>
    </main>
  );
}
```

**Step 4: 运行测试并确认通过**

Run: `cd apps/desktop && npm test -- App.test.tsx`
Expected: PASS

**Step 5: 提交**

```bash
git add apps/desktop/src
git commit -m "feat: 搭建桌面端最小交互壳"
```

### Task 11: 接通前后端唤醒链路

**Files:**
- Modify: `apps/desktop/src/lib/api.ts`
- Modify: `apps/desktop/src/App.tsx`
- Create: `services/core/tests/test_integration_wake.py`

**Step 1: 写失败测试**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_wake_endpoint_returns_thought():
    client = TestClient(app)
    response = client.post("/lifecycle/wake")
    body = response.json()
    assert body["mode"] == "awake"
    assert body["current_thought"]
```

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_integration_wake.py -v`
Expected: FAIL because response shape lacks `current_thought` or UI path is not wired

**Step 3: 写最小实现**

```ts
export async function wake() {
  const response = await fetch("http://localhost:8000/lifecycle/wake", {
    method: "POST",
  });
  return response.json();
}
```

```tsx
import { useState } from "react";
import { wake } from "./lib/api";

export default function App() {
  const [thought, setThought] = useState("");

  async function handleWake() {
    const result = await wake();
    setThought(result.current_thought ?? "");
  }

  return (
    <main>
      <button onClick={handleWake}>Wake</button>
      <p>{thought}</p>
    </main>
  );
}
```

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_integration_wake.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add apps/desktop/src services/core/tests/test_integration_wake.py
git commit -m "feat: 打通唤醒交互链路"
```

### Task 12: 为世界模拟预留扩展接口

**Files:**
- Create: `services/core/app/world/models.py`
- Create: `services/core/app/world/service.py`
- Create: `services/core/tests/test_world_service.py`

**Step 1: 写失败测试**

```python
from app.world.service import WorldStateService


def test_world_state_bootstraps_daily_rhythm():
    service = WorldStateService()
    state = service.bootstrap()
    assert state.time_of_day in {"morning", "afternoon", "evening", "night"}
```

**Step 2: 运行测试并确认失败**

Run: `cd services/core && pytest tests/test_world_service.py -v`
Expected: FAIL with missing world modules

**Step 3: 写最小实现**

```python
from pydantic import BaseModel


class WorldState(BaseModel):
    time_of_day: str
```

```python
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
```

**Step 4: 运行测试并确认通过**

Run: `cd services/core && pytest tests/test_world_service.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/world services/core/tests/test_world_service.py
git commit -m "feat: 预留世界模拟基础接口"
```

## 执行说明

优先顺序应为：

1. 后端领域模型与生命周期
2. 记忆与模型网关
3. 自主循环与工具沙箱
4. 桌面端界面与联调
5. 世界模拟预留接口

所有任务都应遵守：

- 每次只做一个步骤
- 每步先测试失败，再写最小实现
- 每个任务完成后立刻运行对应测试
- 如果仓库尚未初始化 git，先执行 `git init`
