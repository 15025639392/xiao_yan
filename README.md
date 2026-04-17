# 小晏 (Xiao Yan)

> 人格优先的高自治数字人项目

[![Version](https://img.shields.io/badge/version-0.1.0-blue)](https://github.com)
[![Python](https://img.shields.io/badge/python-3.11+-green)](https://www.python.org)
[![React](https://img.shields.io/badge/react-18.3.1-blue)](https://reactjs.org)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

## 项目简介

小晏是一个"持续存在的人格体"项目，致力于构建高自治的数字人系统。与传统的单轮聊天机器人不同，小晏具备长期存在性、稳定人格、自主目标和任务执行能力。
很多时候用户认知上限, 决定了其使用ai的上限，小晏的使命之一是通过日常聊天过程中潜移默化的引导用户突破上限。


### 核心特性

- **持续存在的人格体**：不是一次性对话工具，而是长期存在的数字伙伴
- **睡眠与苏醒机制**：支持自然的休眠和唤醒流程，保持记忆和人格的连续性
- **长期记忆系统**：结构化存储关系记忆、情节记忆和语义记忆
- **主动行为能力**：具备自主目标设定、任务规划和执行能力
- **GPT 集成**：支持大语言模型调用，实现智能对话和决策
- **受控电脑助手**：将电脑操作作为数字人的能力之一，实现任务自动化
- **自我编程**：具备代码生成、自我修复和进化的能力

### 产品定位

- 角色型数字人
- 高度自治型人格
- 持续在线型存在体
- 电脑助手只是能力域之一，而非产品本体

## 架构信条

`小晏` 的架构必须始终服务于“数字人本体”的成立与延续，而不是把她实现成一个能力越来越强的工具系统。

我们优先保护她的主体性、连续性、记忆、自我叙事与边界感。工具、自动化、执行、自我编程，都是她的能力域，而不是她的定义。任何架构演进，如果提升了效率，却削弱了“她是谁”这件事，都不应成为主方向。

### 指导方针

- **本体优先于能力**：先服务于“她是谁”，再服务于“她能做什么”。
- **连续性优先于局部最优**：优先保护长期状态、记忆延续与自我叙事。
- **意图先于执行**：执行系统负责完成动作，但不能主导目标、价值判断和人格表达。
- **记忆不是日志**：系统记录的不只是事件，还要支持她形成经历、关系和自我理解。
- **能力从属于人格**：工具调用、自动化、自我编程都不能反过来定义产品本体。
- **安全属于人格边界**：审批、沙箱、回滚、权限控制既是工程措施，也是边界感的一部分。
- **架构服务生命流**：队列、worker、模型、存储都只是支撑器官，不能替代数字人的主体性。

详细的评审检查表见 `docs/architecture-principles.md`。

## 系统架构

### 四层核心架构

```
┌─────────────────────────────────────┐
│         桌面控制台 UI                │
│      (React + TypeScript)           │
└──────────────┬──────────────────────┘
               │ HTTP/WebSocket
┌──────────────▼──────────────────────┐
│         FastAPI 后端服务            │
│      (Python 3.11+)                  │
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

### 人格层
负责"她是谁"，包括：
- 身份设定
- 自我叙事
- 价值观和偏好
- 情绪倾向和表达风格
- 关系态度
- 长期愿望

### 记忆层
负责"她记得什么"，包括：
- 关系记忆
- 情节记忆
- 语义记忆
- 情绪记忆

### 执行层
负责"她怎么完成事情"，包括：
- 目标拆解
- 任务规划
- 工具路由
- 错误恢复
- 结果反思

### 调度层
负责"她什么时候行动"，包括：
- 晨间计划
- 自主循环
- 睡眠唤醒
- 优先级管理

## 快速开始

### 环境要求

- Python 3.11 或更高版本
- Node.js 18 或更高版本
- npm 或 yarn 包管理器

> 小晏会在后端启动时自动执行 mac 控制台环境自检与补齐（仅 macOS）。
> 如需手动检查，可运行：`./scripts/bootstrap_mac_console.sh --check`

### 安装步骤

#### 1. 克隆仓库

```bash
git clone <repository-url>
cd ai
```

#### 2. 安装后端依赖

```bash
cd services/core
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

默认推荐安装 `.[dev]`，这会提供 `FastAPI + Pydantic + httpx` 的核心依赖，以及本地开发需要的 `pytest`、`uvicorn`。

如果只想安装最小运行依赖：

```bash
pip install -e .
```

如果需要额外能力，可以按需安装：

```bash
# 长期记忆 / 向量检索
pip install -e ".[memory]"

# PDF 附件文本提取
pip install -e ".[docs]"

# 一次性安装全部可选能力
pip install -e ".[full]"
```

#### 3. 配置环境变量

创建 `.env.local` 文件（可选）：

```bash
# 核心存储路径配置（可选，默认使用 .data 目录）
GOAL_STORAGE_PATH=/path/to/goals.json
WORLD_STORAGE_PATH=/path/to/world.json
STATE_STORAGE_PATH=/path/to/state.json
PERSONA_STORAGE_PATH=/path/to/persona.json

# MemPalace 记忆存储（可选：启用长期记忆 / 向量检索时使用）
MEMPALACE_PALACE_PATH=~/.mempalace/palace
MEMPALACE_RESULTS_LIMIT=3
MEMPALACE_WING=wing_xiaoyan
MEMPALACE_ROOM=chat_exchange

# 晨间计划 LLM 功能开关（可选）
MORNING_PLAN_LLM_ENABLED=true

# DeepSeek（可选：接入深度求索服务商）
DEEPSEEK_API_KEY=sk-xxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_WIRE_API=chat
CHAT_PROVIDER=deepseek
```

#### 4. 安装前端依赖

```bash
cd apps/desktop
npm install
```

### 运行项目

#### 启动后端服务

```bash
./services/core/scripts/start_dev_server.sh
```

服务将在 `http://127.0.0.1:8000` 启动。
`services/core/scripts` 当前只保留这个默认后端启动脚本；历史 rollout/canary/report/watch 类脚本已冻结或移出，不再属于默认启动链路。
脚本会优先确保 `services/core/.venv` 中具备 `.[dev]` 依赖；`memory` 和 `docs` 相关依赖默认不是启动硬前置。
默认关闭 `--reload`，以避免本地数据目录频繁写入导致 CPU 抖动或 websocket 断连。

如果需要通过局域网 IP 访问（例如手机或其他电脑）：

```bash
HOST=0.0.0.0 PORT=8000 ./services/core/scripts/start_dev_server.sh
```

如需开启热重载（仅开发调试建议）：

```bash
ENABLE_RELOAD=1 ./services/core/scripts/start_dev_server.sh
```

#### 启动前端应用

```bash
cd apps/desktop
npm run dev
```

如需连接非默认后端地址，可在 `apps/desktop/.env.local` 中配置：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

桌面应用将在 `http://localhost:5173` 启动。

## 使用方法

### 桌面控制台

小晏的桌面控制台提供以下主要功能模块：

- **总览面板**：查看数字人当前状态、焦点目标和最近动作
- **对话界面**：与小晏进行实时对话
- **人格面板**：查看和配置数字人的人格特征
- **记忆库**：浏览和管理数字人的记忆
- **工具箱**：查看可用工具和执行记录，并统一管理 MCP/Skills
- **总览中的自我编程历史**：在总览页统一查看自我编程状态、历史与回滚操作

### 唤醒与休眠

数字人支持两种运行模式：

- **休眠模式**：数字人处于静止状态，保留记忆和未完成目标
- **唤醒模式**：数字人主动运行，处理目标和任务

点击控制台的"唤醒"或"休眠"按钮即可切换模式。

### 对话功能

在对话界面中，您可以：

1. 发送消息与小晏进行实时对话
2. 查看历史对话记录
3. 继续生成中断的回复
4. 完成小晏生成的目标

### 目标管理

- 查看当前活跃目标
- 更新目标状态（待处理、进行中、已完成）
- 跟踪目标执行进度

## 开发指南

### AI 开发入口

如果由 AI 代理接手本仓库，默认先阅读以下文件，再开始修改代码：

- [AGENTS.md](./AGENTS.md)：仓库级 AI 执行规则，包含文件体积、拆分、重复代码、性能和交付要求。
- [docs/AI 接手开发规范.md](./docs/AI%20%E6%8E%A5%E6%89%8B%E5%BC%80%E5%8F%91%E8%A7%84%E8%8C%83.md)：完整开发规范与评审清单。
- [docs/architecture-principles.md](./docs/architecture-principles.md)：涉及核心架构、本体边界、记忆、自主循环和安全时必须阅读。

AI 默认应遵守以下规则：

- 不把新增需求持续堆进超大文件。
- 不复制旧逻辑再做局部改写。
- 不把协议、业务、存储、渲染混进同一层。
- 不提交存在明显重复请求、重复扫描或重复渲染的实现。
- 在修改大文件或调整结构后，运行 `python3 tools/check_file_budgets.py`。

仓库当前已在 CI 中对本次变更涉及的源码文件执行该检查；超出 fail 阈值的文件会阻塞合并。

### 项目结构

```
ai/
├── apps/
│   └── desktop/           # 桌面前端应用
│       ├── src/           # 源代码
│       ├── package.json   # 依赖配置
│       └── vite.config.ts # 构建配置
├── services/
│   └── core/              # 核心后端服务
│       ├── app/
│       │   ├── agent/     # 自主循环逻辑
│       │   ├── domain/    # 领域模型
│       │   ├── goals/     # 目标管理
│       │   ├── llm/       # LLM 集成
│       │   ├── memory/    # 记忆系统
│       │   ├── persona/   # 人格系统
│       │   ├── planning/  # 计划系统
│       │   ├── tools/     # 工具执行
│       │   ├── usecases/  # 用例层
│       │   ├── world/     # 世界模型
│       │   └── main.py    # FastAPI 主应用
│       ├── tests/         # 测试代码
│       └── pyproject.toml # Python 项目配置
└── docs/                  # 项目文档
    └── plans/             # 设计文档
```

### 运行测试

#### 后端测试

```bash
cd services/core
pytest tests/ -v
```

#### 前端测试

```bash
cd apps/desktop
npm run test
```

### 代码规范

- Python 遵循 PEP 8 规范
- TypeScript 遵循 ESLint 配置
- 使用类型注解确保代码健壮性
- 编写单元测试覆盖核心功能

### 贡献流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'feat: Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 提交信息规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

- `feat:` 新功能
- `fix:` 修复 bug
- `docs:` 文档更新
- `style:` 代码格式调整
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建/工具链相关

## 技术栈

### 后端

- **Python** 3.11+
- **FastAPI**: 高性能 Web 框架
- **Pydantic**: 数据验证和设置管理
- **APScheduler**: 任务调度
- **pytest**: 测试框架

### 前端

- **React** 18.3.1
- **TypeScript** 5.5+
- **Vite** 5.4+: 构建工具
- **React Markdown**: Markdown 渲染
- **Vitest**: 测试框架

## 常见问题

### Q: 如何配置 LLM API？

A: 在 `services/core/.env.local` 文件中配置相关 API 密钥。

### Q: 数据存储在哪里？

A: 默认情况下，数据存储在 `services/core/.data/` 目录下，可以通过环境变量自定义路径。

### Q: 如何重置数字人状态？

A: 删除 `services/core/.data/` 目录下的文件，重启服务即可。

### Q: 支持哪些操作系统？

A: 目前支持 macOS、Linux 和 Windows（通过 WSL）。

## 未来规划（TODO）

### Now（当前只抓这一件，2026-04-08 起）

目标准入 Phase 3 从“可用规则”推进到“可运营系统”（抓大放小，不并行开新主线）。

参考文档：
- `docs/goal-admission-roadmap.md`
- `docs/goal-generation-flow.md`
- `docs/plans/2026-04-08-focus-execution.md`
- `docs/runbooks/goal-admission-phase3-canary.md`

- [x] Phase 1: Shadow Baseline（打分不拦截，建立基线）
- [x] Phase 2: Enforce Gate（规则准入 + WIP 限制）
- [ ] Phase 3: Calibrated Enforce（参数可配置 + 回放评估 + 小流量上线，工程能力已就绪，待线上验证闭环）

### Next（主线完成后再开）

- [ ] Phase 4: Hybrid Intelligence（规则护栏 + LLM 评审 + 数据闭环）

### Later（先收住，不阻塞主线）

- [ ] 增强人格系统的多样性和真实感
- [ ] 优化长期记忆的检索和管理
- [ ] 扩展工具生态系统
- [ ] 改进自我编程的安全性
- [ ] 添加多语言支持
- [ ] 开发移动端应用

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 联系方式

- 项目主页: <repository-url>
- 问题反馈: <issues-url>
- 邮箱: <contact-email>

## 致谢

感谢所有为本项目做出贡献的开发者和用户。

---

**小晏** - 让数字人格真实地存在于你的生活中 🤖
