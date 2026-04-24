# 对话驱动 VRM 生成方案

## 0) 元信息（必填）

- 需求标题：对话驱动 Blender 生成 VRM 模型
- 需求模式：标准
- 需求来源：用户提出“通过 AI 对话生成 VRM 模型”
- 负责人：项目开发者
- 更新时间：2026-04-24

## 1) 需求摘要

- 背景与目标：用户用自然语言描述数字人外观，系统将描述转换为结构化角色规格，并通过 Blender 自动修改模板模型，最终导出 `.vrm` 文件。
- 用户价值：降低数字人形象制作门槛，让“小晏”的外观可以通过对话进行可控、可复现、可回滚的迭代。
- 成功指标（可量化，至少 1 条）：至少导出 1 个可被 VRM 查看器加载的 `.vrm`，单次 MVP 生成流程控制在 3 到 10 分钟内。

详细指标：
  - 输入一段角色描述后，能生成合法的 `character_spec.json`。
  - 能调用 Blender 脚本修改基础人形模板。
  - 能导出一个可被 VRM 查看器加载的 `.vrm` 文件。
  - 单次 MVP 生成流程控制在 3 到 10 分钟内。
  - 缺少 Blender 或 VRM 插件时，后端核心服务仍可启动并清晰降级。
- 截止时间：MVP 建议 1 到 2 周。
- 非目标（本次明确不做）：第一版不做纯文本直接生成商用级完整 3D 人体，也不自动覆盖小晏默认形象。

详细非目标：
  - 第一版不做纯文本直接生成商用级完整 3D 人体。
  - 第一版不做自动重拓扑、自动高质量权重、复杂布料模拟。
  - 第一版不把 VRM 生成逻辑混入小晏人格核心层。
  - 第一版不直接覆盖小晏默认形象，只生成可确认的草稿版本。

## 2) 范围、依赖与约束

- In-scope：
  - 对话转结构化角色规格。
  - 角色规格 schema 与校验。
  - Blender 外部执行器边界。
  - Blender Python 模板改模脚本。
  - 基础资产库：发型、眼睛、服装、材质、表情预设。
  - VRM 导出流程。
  - 生成任务状态、失败日志、产物路径管理。
- Out-of-scope：
  - 完全从零生成高质量人形拓扑。
  - 自动商用授权判断。
  - 大规模资产 marketplace。
  - 无人工确认地替换小晏正式形象。
- 上游依赖：
  - LLM provider。
  - Blender。
  - Blender VRM Add-on 或 Unity UniVRM。
  - 基础人形模板模型。
  - 可复用的发型、服装、眼睛和材质资产。
- 下游影响：
  - 桌面端可新增 VRM 生成页面或生成记录入口。
  - 小晏形象系统可引用生成出的形象版本。
  - 后续可扩展到表情、姿态、服装风格与人格状态的弱绑定。
- 约束：
  - Blender 和 VRM 插件属于外部器官能力，不应成为核心服务硬依赖。
  - 后端核心路径在未配置 Blender 时必须能启动。
  - 生成任务必须可审计、可取消、可回滚。
  - 产物写入必须限制在允许目录内。
  - 不应扩大自主执行权限；替换默认形象必须经过明确确认。
- 前置假设：
  - MVP 使用本地 Blender 执行，不先做云端渲染队列。
  - MVP 使用一个固定基础女性人形模板。
  - MVP 风格优先二次元或半写实，不追求影视写实。

## 3) 待确认问题（必填，逐条状态）

| ID | 问题 | 状态 | Owner | 截止时间 | 风险 |
| --- | --- | --- | --- | --- | --- |
| Q1 | 第一版目标风格是二次元、半写实，还是写实？ | 待确认 | 用户 | MVP 开发前 | 影响模板和资产库选择 |
| Q2 | 是否已有基础 VRM 或 Blender 人形模板？ | 待确认 | 用户 | MVP 开发前 | 没有模板会增加工期 |
| Q3 | 导出路径优先用 Blender VRM Add-on 还是 Unity UniVRM？ | 有风险假设 | 开发者 | 技术预研后 | 影响自动化复杂度 |
| Q4 | 是否需要第一版做前端 3D 实时预览？ | 待确认 | 用户 | M2 前 | 影响桌面端工作量 |
| Q5 | 生成模型是否需要商用授权链路？ | 待确认 | 用户 | 发布前 | 影响资产来源和许可证记录 |

## 4) 方案对比（A/B，必要时 C）

| 维度 | 方案 A | 方案 B | 方案 C |
| --- | --- | --- | --- |
| 实现复杂度 | 中，模板参数化生成 | 高，AI 生成 Mesh 后转 VRM | 低到中，VRoid 半自动流程 |
| 交付速度 | 快 | 慢 | 快 |
| 风险等级 | 低到中 | 高 | 中 |
| 回滚成本 | 低 | 高 | 中 |
| 可维护性 | 高 | 低 | 中 |
| 模型质量稳定性 | 高 | 不稳定 | 较高 |
| 自动化程度 | 高 | 中 | 低到中 |
| 适合小晏连续身份 | 高 | 低 | 中 |

- 推荐方案：方案 A，模板参数化生成。
- 推荐理由：
  - 输出可控，符合小晏“连续身份优先”的产品方向。
  - 可以从最小可运行闭环开始，后续逐步积累资产库。
  - 每次生成都有规格文件和产物记录，便于审计和回滚。
  - 缺少 Blender 时可以降级为“生成规格草稿”，不影响核心服务启动。
  - 比纯 AI Mesh 生成更容易保证骨骼、表情和 VRM 标准。
- 不选其他方案的关键原因：方案 B 的拓扑、绑定、表情和兼容性不可控；方案 C 的对话式脚本自动化能力弱。

不选其他方案明细：
  - 不选方案 B：AI 生成 Mesh 的拓扑、绑定、表情和 VRM 兼容性不可控，第一版风险过高。
  - 不选方案 C：VRoid 适合人工捏人，但对话式脚本自动化能力弱，不适合作为长期主链路。

## 5) 推荐系统架构

```text
apps/desktop
  └─ VRM 生成页面 / 生成记录 / 预览入口
       ↓ HTTP
services/core
  └─ app/api/vrm_generation.py
       ↓
  └─ app/usecases/vrm_generation/
       ├─ spec_service.py          # 对话转 character_spec.json
       ├─ job_service.py           # 生成任务编排
       ├─ artifact_repository.py   # 产物记录与路径管理
       └─ blender_executor.py      # 外部 Blender 调用边界
       ↓ subprocess
external Blender
  └─ scripts/generate_vrm.py
       ├─ 加载基础模板
       ├─ 应用体型、材质、发型、服装参数
       ├─ 配置表情、Meta、LookAt、Spring Bone
       └─ 导出 .vrm
```

边界原则：

- `services/core` 只负责任务、规格、审计和产物管理。
- Blender 是外部执行器，不进入人格核心层。
- VRM 生成结果是外观资产，不是人格状态本身。
- 新形象默认进入草稿版本，不能自动替换小晏默认形象。
- 缺少 Blender 时返回能力不可用或仅生成规格草稿，不能导致服务不可用。

## 6) 角色规格结构

`character_spec.json` 是 LLM 输出和 Blender 脚本之间的稳定协议。

```json
{
  "identity": {
    "name": "小晏",
    "style": "soft_anime",
    "age_impression": "young_adult",
    "personality_visual_keywords": ["温柔", "安静", "亲近感"]
  },
  "body": {
    "height": 0.94,
    "head_size": 1.06,
    "shoulder_width": 0.9,
    "body_type": "slim"
  },
  "face": {
    "eye_color": "#7fb8ff",
    "eye_shape": "soft",
    "mouth_default": "gentle_smile",
    "skin_tone": "#f7d8c8"
  },
  "hair": {
    "style": "short_bob",
    "color": "#b98a5a",
    "physics": "light"
  },
  "clothes": {
    "preset": "home_dress",
    "primary_color": "#ffffff",
    "secondary_color": "#d9ecff"
  },
  "expressions": {
    "default": "soft_smile",
    "required": ["happy", "sad", "blink", "surprised", "thinking"]
  },
  "vrm": {
    "version": "1.0",
    "author": "xiao_yan_project",
    "license": "private_prototype"
  }
}
```

校验要求：

- 枚举字段必须限制在资产库已有项中，例如 `hair.style`、`clothes.preset`。
- 颜色必须是合法 hex 色值。
- 比例字段必须在安全范围内，例如 `height` 建议 `0.85` 到 `1.15`。
- `vrm.license` 第一版可固定为 `private_prototype`。
- 规格校验失败时不能执行 Blender。

## 7) 生成任务状态

```text
queued
→ parsing_spec
→ validating_spec
→ running_blender
→ exporting_vrm
→ completed
→ failed
→ cancelled
```

状态约束：

- `failed` 必须保留失败阶段、错误摘要和日志路径。
- `cancelled` 必须尽力终止外部 Blender 进程。
- `completed` 必须记录 `.vrm` 产物路径和使用的规格快照。
- 任务状态不能依赖内存单点，至少应落盘 JSON 记录。

## 5) 任务拆分（必填）

| 任务ID | 任务描述 | 优先级 | 预计工时 | Owner | 依赖任务 | 阻塞条件 | 影响文件/模块 | 验收命令 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | 确认模板模型、目标风格和导出插件 | P0 | S | 用户/开发者 | 无 | 无基础模板 | `docs/plans`、资产目录 | 手动打开模板并记录插件版本 | 中 |
| T2 | 定义 `character_spec.json` schema 与示例 | P0 | S | 开发者 | T1 | 风格范围未定 | `services/core/app/usecases/vrm_generation` | `uv run --project services/core pytest tests/ -k vrm_spec` | 低 |
| T3 | 实现对话转角色规格服务 | P0 | M | 开发者 | T2 | LLM 配置不可用 | `services/core/app/usecases/vrm_generation/spec_service.py` | `uv run --project services/core pytest tests/ -k vrm_spec` | 中 |
| T4 | 实现 Blender 外部执行器边界 | P0 | M | 开发者 | T2 | 本机无 Blender | `services/core/app/usecases/vrm_generation/blender_executor.py` | `uv run --project services/core pytest tests/ -k vrm_executor` | 中 |
| T5 | 编写 Blender 模板改模脚本 | P0 | L | 开发者/美术 | T1/T2 | 模板骨骼不规范 | `services/core/scripts/vrm_generation/generate_vrm.py` | 手动导出并加载 `.vrm` | 高 |
| T6 | 实现生成任务 API | P1 | M | 开发者 | T3/T4 | 任务状态未定义 | `services/core/app/api/vrm_generation.py` | `uv run --project services/core pytest tests/ -k vrm_generation` | 中 |
| T7 | 实现生成记录和产物仓储 | P1 | S | 开发者 | T6 | 存储路径未定 | `services/core/app/usecases/vrm_generation/artifact_repository.py` | `uv run --project services/core pytest tests/ -k vrm_artifact` | 低 |
| T8 | 实现桌面端最小生成页面 | P1 | M | 开发者 | T6 | API 未稳定 | `apps/desktop/src` | `npm test -- vrm` | 中 |
| T9 | 加入 VRM 查看器加载验证 | P2 | M | 开发者 | T5/T6 | 缺少预览方案 | 前端或验证脚本 | 手动加载 `.vrm` | 中 |

## 9) MVP 里程碑

### M0：技术预研，1 到 2 天

目标：

- 确认 Blender 可以 headless 执行。
- 确认 VRM 插件可以脚本化导出。
- 确认基础模板能被自动修改并再次导出。

交付物：

- `character_spec.example.json`
- `generate_vrm.py` 原型脚本
- `xiao_yan_test.vrm`

### M1：后端任务闭环，2 到 3 天

目标：

- 提供 API 创建生成任务。
- LLM 或规则生成角色规格。
- 调用 Blender 执行脚本。
- 保存生成产物和日志。

建议接口：

- `POST /api/vrm-generation/jobs`
- `GET /api/vrm-generation/jobs/{job_id}`
- `POST /api/vrm-generation/jobs/{job_id}/cancel`
- `GET /api/vrm-generation/jobs/{job_id}/artifacts`

### M2：桌面端最小页面，2 到 3 天

目标：

- 用户输入自然语言描述。
- 显示生成状态。
- 展示产物路径和错误信息。
- 支持重新生成。

### M3：小晏人格联动，后续阶段

目标：

- 从人格设定生成默认视觉关键词。
- 让外观变化进入确认流，而不是自动替换身份。
- 支持形象版本记录。

## 6) 验收用例矩阵（必填，测试化）

| 用例ID | 类型 | Given | When | Then | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| A1 | 功能 | 用户输入“小晏，浅棕短发，蓝眼睛，白色居家裙” | 创建生成任务 | 返回任务 ID，状态为 `queued` | 自动 |
| A2 | 功能 | LLM 可用 | 执行规格生成 | 生成合法 `character_spec.json` | 自动 |
| A3 | 功能 | Blender 已配置 | 执行生成任务 | 产出 `.vrm` 文件 | 手动 |
| A4 | 回归 | Blender 未安装 | 创建生成任务 | 后端返回能力不可用，不影响服务启动 | 自动 |
| A5 | 回归 | 用户输入要求写入任意系统路径 | 执行生成任务 | 被限制到允许的产物目录 | 自动 |
| A6 | 回归 | 生成 `.vrm` 完成 | 用 VRM 查看器加载 | 模型可加载，基础表情可触发 | 手动 |
| A7 | 性能 | 模板资产存在 | 连续生成 3 次 | 无无限轮询、无未清理临时文件 | 手动 |
| A8 | 功能 | 小晏已有默认形象 | 用户生成新形象 | 新形象作为草稿版本，不直接覆盖默认形象 | 自动 |

## 7) 发布与回滚（标准/发布级必填）

- Done 标准：
  - API 可创建、查询、取消生成任务。
  - 生成失败有明确错误原因。
  - 缺少 Blender 时核心服务仍能启动。
  - 至少一个模板能导出可加载 `.vrm`。
  - 生成产物不会写出限定目录。
- 上线门禁：后端相关测试通过、文件体积检查通过、手动加载一次 `.vrm` 成功，并明确 Blender 路径配置和降级行为。

上线门禁明细：
  - 后端相关测试通过。
  - 文件体积检查通过。
  - 手动加载一次 `.vrm` 成功。
  - 明确 Blender 路径配置和降级行为。
- 回滚触发条件：后端启动被 Blender 或插件依赖阻塞、生成任务写入越界路径、资源占用不可控、VRM 产物无法加载。

回滚触发条件明细：
  - 后端启动被 Blender 或插件依赖阻塞。
  - 生成任务写入越界路径。
  - 生成任务造成不可控资源占用。
  - VRM 产物无法被查看器加载。
- 回滚路径：关闭 VRM 生成入口，保留任务记录和日志，删除未发布产物，恢复到仅展示现有形象资产。

回滚路径明细：
  - 关闭 VRM 生成入口。
  - 保留任务记录和日志。
  - 删除未发布产物。
  - 恢复到仅展示现有形象资产。
- 观测指标（D0 / D+1 / D+7）：D0 观察任务成功率、平均耗时和失败类型；D+1 观察重试率和 Blender 失败率；D+7 观察常用参数和人工修正次数。

观测指标明细：
  - D0：任务成功率、平均生成耗时、失败类型。
  - D+1：用户重试率、Blender 调用失败率。
  - D+7：常用风格参数、模型版本保留率、人工修正次数。

## 8) 质量评分（必填）

- 评分卡文件：`/Users/ldy/.codex/skills/requirement-workflow/references/requirement-quality-scorecard.md`
- 当前总分：97/100
- 是否可进入下一阶段：是
- 完整性：25/25
- 可执行性：25/25
- 可验收性：24/25
- 风险覆盖：23/25
- 扣分项：
  - 基础模板来源未确认。
  - 可编辑基础模板仍需确认。
  - 商用授权策略未确认。
  - 前端预览方式未确认。

## 13) 反模式自检

- 伪清晰：已给成功指标、非目标和约束。
- 伪方案对比：已对比 A/B/C，并说明不选其他方案原因。
- 伪任务拆分：任务包含优先级、Owner、依赖、验收命令和风险等级。
- 伪验收：验收用例使用 Given/When/Then，并标注验证方式。
- 伪续跑：下一步唯一是执行 M0 技术预研。
- 伪完成：仍未确认的问题进入待确认表，没有使用空占位伪装完成。

## 14) 下一步（唯一）

执行 M0 技术预研：确认本机 Blender、VRM 导出插件、基础模板模型三项是否可用，并记录最小导出命令。
