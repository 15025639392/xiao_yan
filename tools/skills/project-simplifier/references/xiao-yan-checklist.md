# Xiao Yan Simplification Checklist

这个清单只服务于当前仓库，目标是帮助你快速判断哪些部分应该保留、延后或删除。

## 先看主链路

- 前端入口是否仍然以 `apps/desktop` 为核心。
- 后端启动是否仍然以 `services/core/scripts/start_dev_server.sh` 为主。
- `/chat`、`/runtime`、基础配置接口是否是当前产品闭环的一部分。
- `apps/desktop` 是否默认依赖 orchestrator、memory、persona、tools、history 等多个页签共同成立。

## 优先保留

- `apps/desktop` 中真正参与当前首页、聊天、状态展示的页面和组件。
- `services/core/app/api` 中支撑当前前端默认流程的接口。
- 让项目前后端能稳定启动的脚本与配置。
- 必须存在的数据存储路径与最小配置读取逻辑。

## 优先延后

- 复杂编排工作台与多会话并行能力。
- 自主调度、晨间计划、长期 goal admission 流程。
- 知识库 rollout、灰度观察、canary、release report、replay compare 相关脚本。
- 需要额外外部服务、额外密钥或重型依赖才能体现价值的能力。

## 删除候选信号

- 代码存在，但默认 UI 或默认 API 流程不会触发。
- 需要单独维护文档、脚本、观察报表，但对当前最小版本没有直接收益。
- 增加了心智负担，却不能提升“打开就能用”的体验。
- 依赖重、启动慢、失败点多，但只服务于边缘场景。

## 对当前仓库的默认关注点

- `services/core/app/orchestrator`
- `services/core/app/self_programming`
- `services/core/app/memory` 中重依赖 `mempalace` 与 `chromadb` 的路径
- `services/core/scripts` 是否仍然只保留默认启动脚本，没有重新混入 rollout、canary、report、watch 类脚本
- `apps/desktop/src/pages/OrchestratorPage.tsx`
- `apps/desktop/src/components/orchestrator`
- `docs/requirements` 与 `docs/checkpoints` 中大量历史需求产物

## 一轮收敛时建议的判断顺序

1. 先确认“没有哪些页面和接口，用户仍能完成当前目标”。
2. 再确认“哪些模块只要移出默认导航或默认启动链路，就能显著降复杂度”。
3. 最后才决定是否真的删代码或删依赖。

## 推荐操作方式

- 先移出默认入口，再观察是否还有引用。
- 先让模块变成可选，再决定是否删除。
- 先减少默认依赖，再清理文档和脚本。
- 避免一上来做全局重构。
