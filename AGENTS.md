# AI Working Rules For `xiao_yan`

This file defines the default execution rules for any AI agent modifying this repository.

If a user request conflicts with these rules, pause and ask for confirmation only when the conflict is material. Otherwise, follow these rules by default.

---

## 项目概览

`xiao_yan`（小晏）是一个**人格优先的高自治数字人项目**，致力于构建持续存在、具备稳定人格和自主行为能力的数字生命体，而非传统单轮对话工具或通用自动化平台。

### 核心特性

- **持续存在的人格体**：长期存在的数字伙伴，具备睡眠/苏醒机制
- **长期记忆系统**：结构化存储关系记忆、情节记忆、语义记忆和情绪记忆
- **主动行为能力**：自主行为习惯与牵挂驱动
- **多 LLM 集成**：支持 OpenAI、DeepSeek、MiniMax 等 provider
- **器官化能力模型**：外部工具（如浏览器、文件操作）作为可接入的器官实现，不属于本体组成部分

### 架构信条

- **本体优先于能力**：先服务于"她是谁"，再服务于"她能做什么"
- **工具外置、知识内化**：外部工具是可接入的器官，本体只内化"器官存在、如何接入、接入后能做什么"的知识
- **连续性优先于局部最优**：保护长期状态、记忆延续与自我叙事
- **意图先于执行**：执行系统完成动作，但不主导目标、价值判断和人格表达
- **安全属于人格边界**：审批、沙箱、回滚、权限控制既是工程措施，也是边界感的一部分

详细评审检查表见 `docs/architecture-principles.md`。

---

## 技术栈与架构

### 系统分层

```
┌─────────────────────────────────────┐
│         桌面控制台 UI                │
│      (React 18 + TypeScript)        │
│      Tauri v2 桌面壳层               │
└──────────────┬──────────────────────┘
               │ HTTP/WebSocket
┌──────────────▼──────────────────────┐
│         FastAPI 后端服务            │
│      (Python 3.11+)                 │
└─────┬───────────────────────────────┘
      │
┌─────▼───────────────────────────────┐
│              核心层                  │
│  ┌─────────┐  ┌─────────┐           │
│  │ 人格层  │  │ 记忆层  │           │
│  └─────────┘  └─────────┘           │
│  ┌─────────┐  ┌─────────┐           │
│  │ 执行层  │  │ 调度层  │           │
│  └─────────┘  └─────────┘           │
│       ┌─────────┐                   │
│       │ 工具层  │                   │
│       └─────────┘                   │
└─────────────────────────────────────┘
```

### 后端 (`services/core`)

| 技术 | 版本/说明 | 用途 |
|------|----------|------|
| Python | >= 3.11 | 运行时 |
| FastAPI | >= 0.115.0 | Web 框架 |
| Pydantic | v2 | 数据验证与模型 |
| httpx | >= 0.27.0 | HTTP 客户端 |
| Pillow | >= 10.0.0 | 图像处理 |
| pytest | >= 7.4.0 (dev) | 测试框架 |
| uvicorn | >= 0.30.0 (dev) | ASGI 服务器 |

**可选依赖（不可升格为硬依赖）：**

- `mempalace>=3.1.0` + `chromadb>=0.5,<0.7`：长期记忆/向量检索
- `pypdf>=5,<6`：PDF 附件文本提取

**核心依赖约束：**

- 核心路径在只安装最小依赖（`fastapi + pydantic + httpx`）时必须可启动和工作
- 可选依赖缺失时必须有明确降级行为，不可导致服务不可用
- 禁止在没有充分理由时新增 ORM、任务队列、DI 容器或复杂配置框架

### 前端 (`apps/desktop`)

| 技术 | 版本/说明 | 用途 |
|------|----------|------|
| React | 18.3.1 | UI 框架 |
| TypeScript | >= 5.5.4 | 类型系统 |
| Vite | 5.4+ | 构建工具 |
| Tailwind CSS | v4 | 样式系统 |
| Tauri | v2 | 桌面应用壳层（Rust） |
| Radix UI | ^1.x | 无头组件 |
| Vitest | ^2.1.8 | 测试框架 |

前端通过 HTTP API 与后端通信，开发服务器默认运行在 `http://localhost:5174`。

### 数据存储

- 默认使用 JSON 文件落盘，存储在 `services/core/.data/` 目录下
- 各存储路径可通过环境变量自定义：`WORLD_STORAGE_PATH`、`STATE_STORAGE_PATH`、`PERSONA_STORAGE_PATH`、`CAPABILITY_QUEUE_STORAGE_PATH`
- 长期记忆可选使用 `mempalace` + `chromadb`，存储在 `services/core/.mempalace/`

---

## 目录结构与模块职责

```
xiao_yan/
├── apps/desktop/               # 桌面前端应用
│   ├── src/
│   │   ├── components/         # React 组件（按领域拆分）
│   │   │   ├── chat/           # 聊天相关组件
│   │   │   ├── memory/         # 记忆面板组件
│   │   │   ├── persona/        # 人格面板组件
│   │   │   ├── tools/          # 工具箱组件
│   │   │   ├── world/          # 世界事件组件
│   │   │   ├── status/         # 状态组件
│   │   │   ├── ui/             # 通用 UI 组件（Button, Dialog, Card 等）
│   │   │   └── app/            # 应用级组件与实时更新逻辑
│   │   ├── pages/              # 页面级组件
│   │   ├── lib/                # 业务逻辑与 API 封装
│   │   │   ├── api*.ts         # 各领域 API 调用
│   │   │   ├── capabilities/   # 能力队列相关逻辑
│   │   │   ├── tauri/          # Tauri 桥接封装
│   │   │   └── utils/          # 纯工具函数
│   │   ├── styles/             # CSS 样式（按领域拆分）
│   │   └── test/               # 测试配置
│   ├── src-tauri/              # Tauri Rust 工程
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── services/core/              # 核心后端服务
│   ├── app/
│   │   ├── main.py             # FastAPI 主应用与入口
│   │   ├── config.py           # 配置读取（环境变量 + .env.local）
│   │   ├── config_llm.py       # LLM 相关配置
│   │   ├── api/                # HTTP/WebSocket 协议层（路由、校验、响应封装）
│   │   ├── domain/             # 核心领域模型（保持纯净，不依赖 FastAPI/外部 HTTP）
│   │   ├── agent/              # 自主循环逻辑
│   │   ├── chat/               # 对话系统
│   │   ├── memory/             # 记忆系统（含可选 mempalace/chromadb 适配）
│   │   ├── persona/            # 人格系统
│   │   ├── world/              # 世界模型
│   │   ├── tools/              # 工具执行与沙箱
│   │   ├── capabilities/       # 能力队列与运行时
│   │   ├── mcp/                # MCP 服务集成
│   │   ├── platform_adapters/  # 平台适配器（小红书等）
│   │   ├── channels/           # 外部渠道桥接（微信等）
│   │   ├── safety/             # 安全边界
│   │   ├── llm/                # LLM 网关与多 provider 适配
│   │   ├── runtime_ext/        # 运行时扩展与启动引导
│   │   ├── external_executors/ # 外部执行器
│   │   ├── focus/              # 焦点管理
│   │   ├── usecases/           # 用例层
│   │   └── utils/              # 纯工具函数
│   ├── tests/                  # 测试代码
│   ├── scripts/                # 启动与工具脚本
│   ├── pyproject.toml          # Python 项目配置
│   └── uv.lock                 # uv 锁文件
│
> **注**：以下目录已被移除，不再属于当前架构：
> - `goals/` — 通用目标管理系统与"人格优先"的架构信条冲突。小晏的自主行为由`focus/`（牵挂）和领域特定习惯流驱动，而非外部或系统生成的目标树。
> - `planning/` — 动态计划生成会把小晏退化为工具平台。当前采用领域特定的习惯链（如`XhsTaskChain`），由状态机和时间节律驱动。
> - `orchestrator/` — 调度编排已内聚于`agent/loop.py`的生命节律中，无需独立的中心化调度层。
> - `self_programming/` — 自我调整通过记忆系统（提取、衰减、习惯参数微调）实现，而非直接修改代码。
>
> 相关历史设计文档仍保留在 `docs/plans/` 和 `docs/runbooks/` 中作为档案，但当前运行时不再依赖这些模块。
│
├── docs/                       # 项目文档
│   ├── plans/                  # 设计文档与方案
│   ├── runbooks/               # 操作手册
│   ├── AI 接手开发规范.md       # AI 开发完整规范
│   ├── architecture-principles.md  # 架构原则
│   ├── testing-strategy.md     # 测试策略
│   ├── daily-shortcuts.md      # 日常快捷入口
│   └── ...
│
├── tools/
│   ├── check_file_budgets.py   # 文件体积检查脚本
│   └── skills/                 # 项目级 Claude Code skills
│
└── .github/workflows/          # CI 工作流
```

### 后端目录职责约束

- **`app/api/`**：只负责协议层（参数校验、请求解析、响应封装、错误映射），不承载过重业务规则
- **`app/domain/`**：核心模型与稳定领域概念，保持纯净
- **`app/*/service.py`**：业务编排，可协调 repository/gateway/runtime state，但不混入协议层细节
- **`app/*/repository.py`**：持久化与读取，优先文件实现/标准库，可选基础设施必须封装在 adapter 边界后
- **`app/memory/`**：可选能力（mempalace/chromadb）必须隔离在边缘模块，缺失时必须有降级

---

## 构建与开发命令

### 环境要求

- Python 3.11+
- Node.js 18+
- npm

### 后端

```bash
# 安装依赖（进入 services/core）
cd services/core
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 启动开发服务器（推荐方式）
./services/core/scripts/start_dev_server.sh

# 自定义主机/端口
HOST=0.0.0.0 PORT=8000 ./services/core/scripts/start_dev_server.sh

# 开启热重载（仅开发调试）
ENABLE_RELOAD=1 ./services/core/scripts/start_dev_server.sh
```

服务默认启动在 `http://127.0.0.1:8000`。启动脚本会自动检查并安装 `.venv` 中的 `.[dev]` 依赖；`memory` 和 `docs` 相关依赖不是启动硬前置。

### 前端

```bash
cd apps/desktop
npm install
npm run dev          # 开发服务器，默认 http://localhost:5174
npm run build        # 生产构建
npm run test         # 运行测试（Vitest）

# Tauri 桌面应用模式
npm run tauri:dev
npm run tauri:build
```

### 环境变量配置

后端环境变量读取顺序（仅在不存在的变量时写入）：

1. 当前工作目录下的 `.env.local`
2. `services/core/.env.local`

推荐复制模板后编辑：

```bash
cp services/core/.env.local.example services/core/.env.local
cp apps/desktop/.env.local.example apps/desktop/.env.local
```

最少只需要配置一个可用 LLM provider 的 API key 即可运行。

---

## 代码风格规范

### Python

- 遵循 PEP 8
- 使用类型注解
- 优先使用标准库和现有依赖，新库引入需充分理由
- 使用普通类、函数、`Protocol`、明确构造参数表达依赖关系
- 使用 `Pydantic` 做输入输出和结构化模型
- 使用 `httpx` 调用外部 HTTP 服务
- 使用文件存储或 `sqlite3` 处理轻量持久化

### TypeScript / React

- 严格模式开启（`strict: true`）
- 路径别名 `@/` 映射到 `./src/*`
- UI 组件使用 shadcn/ui 风格（`components.json` 配置）
- 样式使用 Tailwind CSS v4

### 提交信息规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

- `feat:` 新功能
- `fix:` 修复 bug
- `docs:` 文档更新
- `style:` 代码格式调整
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建/工具链相关

---

## 测试策略

### 总体原则

- 前期少量高价值测试，不追求覆盖率数字
- 优先覆盖：API 契约、领域行为规则、可选依赖降级、已修复 bug 的回归测试
- 延后覆盖：频繁变化的 UI 细节、对内部实现绑定很深的 mock-heavy 单测

### 后端测试

```bash
cd services/core
pytest tests/ -v
```

- 测试文件命名：`test_*.py`
- `conftest.py` 提供自动隔离的 `app` fixture，每轮测试后清理 `app.state` 和 `dependency_overrides`
- 优先跑与改动直接相关的测试子集，再考虑扩大范围
- 优先使用 `uv run --project services/core pytest ...` 运行

### 前端测试

```bash
cd apps/desktop
npm test             # Vitest，jsdom 环境
npm test -- <pattern>
```

- 页面级测试优先于细碎组件测试
- 关注：页面挂载后关键数据请求、tab/mode 切换、关键按钮动作、空态/错误态表达

### 文件体积检查

```bash
python3 tools/check_file_budgets.py
```

CI 在 PR 和 push 到 main/master/codex/** 分支时会自动对变更文件执行该检查；超出 fail 阈值的文件会阻塞合并。

---

## 安全与边界

- 高风险动作必须可解释、可中断、可审计、可回退
- 工具/能力审批与沙箱机制不可擅自放宽
- 可选依赖缺失时服务必须仍能启动或清晰降级
- 禁止擅自扩大自动执行权限
- 禁止擅自把可选依赖升级为硬依赖
- CORS 已配置允许 localhost、私有网段及 Tauri 协议（`tauri://localhost` 等）

---

## Source Of Truth

- Read [docs/AI 接手开发规范.md](./docs/AI%20%E6%8E%A5%E6%89%8B%E5%BC%80F%E8%A7%84%E8%8C%83.md) before making substantial code changes.
- Read [docs/architecture-principles.md](./docs/architecture-principles.md) before changing core architecture, runtime flow, memory, autonomy, safety, or orchestration behavior.
- Preserve the product direction: `xiao_yan` is a digital being first, not a generic automation platform.

---

## Non-Negotiable Defaults

- Prefer explicit code over hidden magic.
- Prefer small, local, reversible changes over large rewrites.
- Prefer fewer dependencies and shorter call chains.
- Prefer practical, verifiable delivery over big upfront concepts; start from real pages, real data, and the smallest runnable loop.
- Prefer the smallest clear responsibility per module, function, and component.
- Prefer the fewest stable branches per behavior chain; do not keep old and new implementations in parallel without a clear active need.
- Prefer clear module boundaries over clever abstractions.
- Do not treat file growth as a normal implementation strategy.

---

## File Size Rules

- Backend Python business files should target 300 lines or fewer.
- Backend Python business files over 500 lines should be treated as split candidates.
- Backend Python business files over 800 lines should not receive more logic until a split is considered.
- Frontend pages and container components should target 250 lines or fewer.
- Frontend pages and container components over 400 lines should be treated as split candidates.
- Frontend pages and container components over 600 lines should not receive more logic until a split is considered.
- Functions should usually stay within 40 lines.
- Functions over 60 lines should be reviewed for mixed responsibilities.
- Functions over 100 lines should be split unless they represent a single linear workflow that cannot be simplified further.

---

## Splitting Rules

- If a module, service, function, or component starts handling more than one clear responsibility, split it.
- Split by responsibility first: protocol, orchestration, storage, transformation, rendering.
- Split by domain second: chat, memory, persona, tools, focus.
- Only move logic into `utils` when it is genuinely generic and not domain behavior in disguise.
- If touching an oversized file, prefer extracting one small layer instead of adding more logic into it.

---

## Duplication Rules

- When similar logic appears a second time, evaluate extraction.
- Do not introduce abstractions for hypothetical future reuse.
- Extract stable repeated steps, not vague meta-frameworks.
- Do not copy old logic into a new branch and patch it locally unless there is a strong reason.

---

## Performance Rules

- Avoid repeated HTTP calls, file reads, model calls, or storage reads inside loops.
- Avoid repeated full scans, sorts, serialization, or deserialization of the same data.
- Avoid heavy computation during frontend render.
- Avoid large shared state updates that trigger unrelated rerenders.
- Avoid unbounded polling, logging, history concatenation, or in-memory accumulation on hot paths.
- Reuse results when possible, prefer incremental updates, and limit payload sizes by default.

---

## Dependency And Architecture Rules

- For `services/core`, keep core runtime dependencies centered on `fastapi`, `pydantic`, and `httpx`.
- Do not promote optional capabilities like `mempalace`, `chromadb`, or `pypdf` into hard runtime requirements.
- Do not add ORM, queue, DI container, or heavy config frameworks without a strong repo-specific justification.
- Keep optional capabilities isolated at the edges with clear downgrade behavior.

---

## Required Workflow

Before editing:

- Identify the entry point.
- Identify the related models and dependency chain.
- Check whether tests already cover the path.
- Check whether the target file is already oversized.

During editing:

- Stay on the smallest behavior chain that solves the request.
- Collapse a behavior to one main implementation path when possible; do not leave compatibility or shadow branches behind by default.
- Do not lead with large conceptual layers when a practical end-to-end step can be implemented and verified first.
- Check whether the target unit already violates the minimum-responsibility principle before adding more logic.
- Reuse existing patterns unless there is a clear benefit in changing them.
- Do not mix unrelated cleanup into the same change.

Before finishing:

- Run `python3 tools/check_file_budgets.py` when code structure changed or when touching large files.
- For backend verification, prefer the project-managed environment via `uv` instead of assuming system Python dependencies are available.
- Run backend tests with `uv run --project services/core pytest ...` and prefer relevant test subsets before broadening scope.
- Do not claim `fastapi`, `pytest`, or other backend test dependencies are missing until `uv run --project services/core ...` has been tried.
- Ask whether the change increased file size pressure, duplication, or hot-path cost.
- Update docs when dependencies, startup, config, module responsibilities, or downgrade behavior changed.
- State which tests were run; if not run, state why and what risk remains.

---

## Low-Token Shortcut

For this early-stage project, default to the narrowest useful task shape.

- Prefer one behavior chain per request.
- Prefer an explicit scope in files/modules/routes.
- Prefer reading the target file and related tests before broader docs.
- Prefer relevant test subsets over full-repo validation.
- Prefer 1-2 relevant skills instead of chaining many skills by default.

Recommended request shape:

```text
Goal: <one-sentence goal>
Scope: <files/modules/routes allowed>
Do not: <clear exclusions>
Output: <analyze only / patch code / tests only / plan only>
Verify: <which tests to run or not run>
```

Quick references:

- [docs/daily-shortcuts.md](./docs/daily-shortcuts.md)
- [docs/low-token-collaboration.md](./docs/low-token-collaboration.md)
- [docs/low-token-request-examples.md](./docs/low-token-request-examples.md)

---

## Review Output Expectations

When reporting a completed code change, include:

- Whether any large file was kept stable, reduced, or made worse.
- Whether duplication was reduced, kept flat, or introduced.
- Whether any performance-sensitive path was changed.
- What tests or checks were run.

---

## Hard Stops

- Do not silently introduce a new architecture layer.
- Do not silently keep multiple long-lived branches for the same behavior when one can be deleted.
- Do not silently widen autonomy or execution permissions.
- Do not silently convert optional dependencies into required ones.
- Do not silently turn the product into a tool platform instead of a digital being.
- Do not keep growing a mixed-responsibility file when the change should live in a smaller unit.
- Do not continue inflating already oversized files just because that is the fastest path.
