---
name: core-change-entrypoint
description: 用于在修改 xiao_yan 后端或主链路前快速定位入口、依赖链、测试覆盖和文件体积风险。适合动 services/core、API 路由、service/repository、状态模型、主链路逻辑前使用，避免 AI 没看清入口就往大文件里继续堆逻辑。
---

# Core Change Entrypoint

在准备改 `services/core` 或主链路时使用本 skill。

尤其适合：

- 改 API 路由
- 改 service / repository / gateway
- 改状态模型或持久化结构
- 改 chat / memory / goals / world / persona / tools 主链路
- 改 bug 但还不清楚入口和依赖链

## 目标

先回答“该改哪里”，再回答“怎么改”。

本 skill 的重点不是给方案，而是先压缩搜索空间，防止：

- 误改入口
- 漏掉真实依赖链
- 在大文件里继续塞逻辑
- 没看测试就重写行为

## 低 Token 默认做法

项目初期默认按最小搜索面执行：

- 先看目标文件，再看相关测试
- 只追最短依赖链，不顺手扫同域所有模块
- 非必要不读额外 plans 或 runbooks
- 如果用户已明确给出范围，不主动扩到全仓
- 如果本轮只需要定位入口，可以停在入口与落点，不默认继续编码

## 默认工作流

1. 识别用户描述对应的入口。
   - HTTP / WebSocket 问题，先看 `services/core/app/api`
   - 业务决策问题，继续追到对应 `service.py`
   - 持久化 / 文件 / 适配问题，继续追到 `repository.py` 或 adapter
   - 状态 / 模型问题，继续追到 `domain`、`models.py` 或 `.data`
2. 列出最短依赖链：
   - entrypoint
   - service
   - repository / adapter / gateway
   - model / state file
3. 检查现有测试是否覆盖这条链。
   - 先用 `rg` 找相关测试
   - 记录是已有覆盖、部分覆盖还是无覆盖
4. 检查目标文件是否已经过大。
   - 超过规范阈值时，优先考虑提取更小承载点
   - 不要默认把新逻辑继续塞进热点文件
5. 判断最小改动落点：
   - `safe_local_edit`
   - `extract_helper_first`
   - `extract_module_first`
6. 只有在落点明确后，才进入编码。

如果用户请求本身已经很窄，可以进一步压缩为：

1. 看目标文件
2. 看直接调用方或被调用方
3. 看相关测试
4. 给出最小落点

## 必须产出

- `入口文件`
- `依赖链`
- `相关模型/状态`
- `测试覆盖`
- `文件体积风险`
- `建议落点`

推荐格式：

- `入口文件: services/core/app/api/...`
- `依赖链: route -> service -> repository -> state`
- `测试覆盖: 已有 2 个相关测试，但缺少错误分支`
- `文件体积风险: 目标 route 文件已超预算，应避免继续堆逻辑`
- `建议落点: extract_helper_first`

## 落点选择规则

- 只是映射、校验、轻微编排差异：`safe_local_edit`
- 需要新增一段可独立命名的纯逻辑：`extract_helper_first`
- 目标文件已明显混合职责，且这次改动会再加一个职责方向：`extract_module_first`

## 常见检查清单

- 入口是否真的是当前用户路径会经过的那个，而不是同名旁路实现
- route 层是否掺了过多业务逻辑
- service 层是否同时做了存储细节和协议映射
- repository 是否把可选依赖泄漏进核心域
- 改动是否会波及 `.data` 中的现有状态文件

## 强约束

- 没找清入口前，不要直接改代码。
- 没过依赖链前，不要假设某个 service 是唯一入口。
- 目标文件已超大时，不要把“先修好再说”当成继续堆逻辑的理由。
- 不要把无关清理混进同一轮。
- 如果最终没有跑测试，必须明确是哪一段链路没验证到。
