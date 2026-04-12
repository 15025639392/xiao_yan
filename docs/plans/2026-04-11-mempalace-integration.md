# 小晏 MemPalace 接入实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不改用户侧交互的前提下，把 MemPalace 接入小晏后端，形成“现有关系记忆 + 长期语义记忆”双层架构。

**Architecture:** 现有 `MemoryService` 继续负责关系边界、承诺、偏好与短期上下文；新增 `MemPalaceAdapter` 负责长期语义检索与对话镜像写入。聊天路由在构建 prompt 时合并两层记忆，并且在每轮回复后异步/容错写入 MemPalace，任何外部依赖异常都不影响主链路回复。

**Tech Stack:** FastAPI, Pydantic, pytest, mempalace(chromadb), 当前 `services/core` 运行时注入体系。

**Execution Discipline:** 每个 Task 严格按 `@superpowers:test-driven-development` 执行；最终总回归前执行 `@superpowers:verification-before-completion`。

---

### Task 1: 接入配置与适配器骨架

**Files:**
- Create: `services/core/app/memory/mempalace_adapter.py`
- Modify: `services/core/app/config.py`
- Test: `services/core/tests/test_mempalace_adapter.py`

**Step 1: 写失败测试**

```python
def test_mempalace_adapter_returns_empty_when_disabled():
    adapter = MemPalaceAdapter(enabled=False)
    assert adapter.search_context("星星") == ""
```

**Step 2: 运行测试并确认失败**

Run: `pytest services/core/tests/test_mempalace_adapter.py::test_mempalace_adapter_returns_empty_when_disabled -v`
Expected: FAIL with `ImportError` or `NameError`（适配器尚未实现）

**Step 3: 写最小实现**

```python
class MemPalaceAdapter:
    def __init__(self, enabled: bool = False, palace_path: str | None = None, results_limit: int = 3):
        self.enabled = enabled
        self.palace_path = palace_path
        self.results_limit = results_limit

    def search_context(self, query: str) -> str:
        if not self.enabled or not query.strip():
            return ""
        return ""
```

同时在 `config.py` 增加：
- `get_mempalace_enabled()`
- `get_mempalace_palace_path()`
- `get_mempalace_results_limit()`

**Step 4: 运行测试并确认通过**

Run: `pytest services/core/tests/test_mempalace_adapter.py -v`
Expected: PASS（至少包含 disabled 场景）

**Step 5: 提交**

```bash
git add services/core/app/memory/mempalace_adapter.py services/core/app/config.py services/core/tests/test_mempalace_adapter.py
git commit -m "feat: 增加 MemPalace 适配器与配置骨架"
```

---

### Task 2: Runtime 注入与依赖获取

**Files:**
- Modify: `services/core/app/runtime_ext/bootstrap.py`
- Modify: `services/core/app/api/deps.py`
- Test: `services/core/tests/test_api_chat.py`

**Step 1: 写失败测试**

```python
def test_chat_route_can_access_mempalace_adapter_from_app_state(client):
    # 断言路由执行时不会因缺少 mempalace_adapter 崩溃
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 200
```

**Step 2: 运行测试并确认失败**

Run: `pytest services/core/tests/test_api_chat.py::test_chat_route_can_access_mempalace_adapter_from_app_state -v`
Expected: FAIL（依赖未注入或属性缺失）

**Step 3: 写最小实现**

- 在 `bootstrap.py` 初始化 `MemPalaceAdapter` 并挂载：`target_app.state.mempalace_adapter`
- 在 `deps.py` 增加 `get_mempalace_adapter(request: Request)`，支持回退到 `enabled=False` 实例

**Step 4: 运行测试并确认通过**

Run: `pytest services/core/tests/test_api_chat.py::test_chat_route_can_access_mempalace_adapter_from_app_state -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/runtime_ext/bootstrap.py services/core/app/api/deps.py services/core/tests/test_api_chat.py
git commit -m "feat: 注入 MemPalace adapter 到运行时依赖"
```

---

### Task 3: 聊天链路接入长期检索（只读）

**Files:**
- Modify: `services/core/app/api/chat_routes.py`
- Modify: `services/core/app/memory/mempalace_adapter.py`
- Test: `services/core/tests/test_api_chat.py`

**Step 1: 写失败测试**

```python
def test_post_chat_instructions_include_mempalace_context_when_available(...):
    # mock adapter.search_context -> "【长期记忆检索】..."
    # 断言传给 gateway 的 instructions 包含该片段
    assert "【长期记忆检索】" in captured_instructions
```

**Step 2: 运行测试并确认失败**

Run: `pytest services/core/tests/test_api_chat.py::test_post_chat_instructions_include_mempalace_context_when_available -v`
Expected: FAIL（当前 instructions 不含长期记忆）

**Step 3: 写最小实现**

- `MemPalaceAdapter.search_context()` 调用 `mempalace.searcher.search_memories()` 并格式化为 prompt 片段
- `chat_routes.py` 在 `memory_context` 之后拼接 `mempalace_context`
- 保证容错：任何异常返回空串，不影响主回复

**Step 4: 运行测试并确认通过**

Run: `pytest services/core/tests/test_api_chat.py::test_post_chat_instructions_include_mempalace_context_when_available -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/api/chat_routes.py services/core/app/memory/mempalace_adapter.py services/core/tests/test_api_chat.py
git commit -m "feat: 聊天提示注入 MemPalace 长期检索上下文"
```

---

### Task 4: 对话镜像写入 MemPalace（只改后端）

**Files:**
- Modify: `services/core/app/memory/mempalace_adapter.py`
- Modify: `services/core/app/api/chat_routes.py`
- Test: `services/core/tests/test_api_chat.py`

**Step 1: 写失败测试**

```python
def test_post_chat_mirrors_exchange_to_mempalace_when_enabled(...):
    # mock adapter.record_exchange
    # 调用 /chat 后断言被调用 1 次，参数包含 user_message + assistant_output
    assert adapter.record_exchange.call_count == 1
```

**Step 2: 运行测试并确认失败**

Run: `pytest services/core/tests/test_api_chat.py::test_post_chat_mirrors_exchange_to_mempalace_when_enabled -v`
Expected: FAIL（当前未写入 MemPalace）

**Step 3: 写最小实现**

- 在 adapter 增加 `record_exchange(user_message, assistant_response, assistant_session_id)`
- 内部调用 MemPalace 写入接口（`add_drawer` 或直接 collection.upsert）
- `chat_routes.py` 在 `output_text` 确认后调用写入，异常仅记录日志，不中断回复

**Step 4: 运行测试并确认通过**

Run: `pytest services/core/tests/test_api_chat.py::test_post_chat_mirrors_exchange_to_mempalace_when_enabled -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/memory/mempalace_adapter.py services/core/app/api/chat_routes.py services/core/tests/test_api_chat.py
git commit -m "feat: 将对话镜像写入 MemPalace 长期记忆"
```

---

### Task 5: 保护与回退（稳定性闸门）

**Files:**
- Modify: `services/core/app/memory/mempalace_adapter.py`
- Modify: `services/core/app/api/chat_routes.py`
- Test: `services/core/tests/test_api_chat.py`
- Test: `services/core/tests/test_mempalace_adapter.py`

**Step 1: 写失败测试**

```python
def test_chat_still_returns_200_when_mempalace_search_raises(...):
    # mock search_context 抛异常
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 200
```

```python
def test_chat_still_returns_200_when_mempalace_record_raises(...):
    # mock record_exchange 抛异常
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 200
```

**Step 2: 运行测试并确认失败**

Run: `pytest services/core/tests/test_api_chat.py -k "mempalace_search_raises or mempalace_record_raises" -v`
Expected: FAIL（未做容错）

**Step 3: 写最小实现**

- `search_context`、`record_exchange` 两侧包裹 try/except
- 捕获后降级为空上下文/跳过写入
- 写入 warning 日志，便于后续观测

**Step 4: 运行测试并确认通过**

Run: `pytest services/core/tests/test_api_chat.py services/core/tests/test_mempalace_adapter.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add services/core/app/memory/mempalace_adapter.py services/core/app/api/chat_routes.py services/core/tests/test_api_chat.py services/core/tests/test_mempalace_adapter.py
git commit -m "fix: 增加 MemPalace 读写容错与降级路径"
```

---

### Task 6: 验收回归与上线步骤

**Files:**
- Modify: `services/core/.env.local`（仅本地验证）
- Modify: `docs/runbooks/mempalace-rollout.md`

**Step 1: 写失败测试（验收脚本）**

```bash
# 目标：先让验证清单不可用（文件不存在）
ls docs/runbooks/mempalace-rollout.md
```

**Step 2: 运行并确认失败**

Run: `test -f docs/runbooks/mempalace-rollout.md`
Expected: 非 0 退出码

**Step 3: 写最小实现**

- 增加 runbook：安装、环境变量、灰度步骤、回滚开关
- 本地配置：
  - `MEMPALACE_ENABLED=true`
  - `MEMPALACE_PALACE_PATH=~/.mempalace/palace`
  - `MEMPALACE_RESULTS_LIMIT=3`

**Step 4: 运行验证并确认通过**

Run:
- `pytest services/core/tests/test_api_chat.py services/core/tests/test_mempalace_adapter.py -q`
- `pytest services/core/tests/test_autonomy_loop.py services/core/tests/test_prompt_builder.py -q`
Expected: 全绿

**Step 5: 提交**

```bash
git add docs/runbooks/mempalace-rollout.md services/core/.env.local
git commit -m "docs: 增加 MemPalace 接入与灰度回滚手册"
```

---

## 执行顺序与里程碑

1. **里程碑 A（半天）**：完成 Task 1-2，系统可启动且默认关闭。
2. **里程碑 B（1 天）**：完成 Task 3，只读检索上线，验证 prompt 增强无回归。
3. **里程碑 C（1 天）**：完成 Task 4-5，写入镜像 + 容错闸门。
4. **里程碑 D（半天）**：完成 Task 6，形成可回滚上线手册。

## 上线守护指标（必须观测）

- `/chat` P95 延迟增量 < 120ms（启用长期检索后）
- `/chat` 5xx 比例不升高
- MemPalace 查询异常率 < 1%
- Prompt 平均长度增量 < 20%（避免挤占主回复 token）

## 非目标（本轮不做）

- 不改用户侧设置项/开关页面
- 不引入 MCP 客户端协议层
- 不做 KG 深度接入（`kg_add/query` 留到下一轮）
