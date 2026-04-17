---
name: optional-dependency-boundary-check
description: 用于检查 xiao_yan 仓库里的可选依赖是否被错误地扩散进核心路径，并评估降级行为是否仍然清晰可用。适合修改 mempalace、chromadb、pypdf、外部适配层、repository、启动依赖或导入链时使用，帮助 AI 守住“可选能力在边缘，核心路径可独立运行”的边界。
---

# Optional Dependency Boundary Check

在涉及可选依赖、外部能力适配层或降级逻辑时使用本 skill。

尤其适合：

- 改 `services/core/app/memory`
- 改 `repository.py`、adapter、gateway
- 改 `mempalace`、`chromadb`、`pypdf` 相关逻辑
- 改启动脚本、依赖声明、导入链
- 改缺失依赖时的错误提示、fallback、degrade 路径

## 目标

确认“可选能力仍是可选的”，而不是被慢慢抬成核心硬依赖。

本 skill 优先检查：

- 导入位置是否越界
- 核心路径能否在最小依赖下继续启动
- 缺失依赖时是否有明确降级行为
- 接口是否把可选能力细节泄漏进核心域

## 必读上下文

开始前先读：

- `docs/AI 接手开发规范.md`
- 涉及的依赖声明、模块导入链和目标文件

## 默认工作流

1. 明确这轮涉及的可选依赖是什么，以及它原本应待在什么边界。
2. 找出依赖的真实使用位置：
   - import 在哪里
   - 实例化在哪里
   - 失败处理在哪里
   - 结果如何回流到主链
3. 判断是否存在边界失守：
   - 在核心域直接 import 可选依赖
   - 启动路径默认要求该依赖存在
   - repository / adapter 之外的层开始理解依赖细节
   - 缺失依赖直接导致服务不可启动
4. 检查降级质量：
   - 是否能继续运行
   - 是否有清晰错误信息
   - 是否有明确 fallback
   - 是否需要在文档中说明
5. 给出结论：
   - `boundary_ok`
   - `needs_isolation`
   - `needs_degrade_path`
   - `becoming_required_risk`
6. 如果要修改，优先把依赖使用收回边缘层，不要把适配细节继续向内扩散。

## 必须产出

- `依赖对象`
- `当前边界`
- `风险判断`
- `降级状态`
- `建议动作`

推荐格式：

- `依赖对象: mempalace`
- `当前边界: memory adapter + optional repository branch`
- `风险判断: needs_isolation`
- `降级状态: 缺依赖时仍可启动，但错误提示不清楚`
- `建议动作: 把 import 收回 adapter，补清晰 fallback 文案与测试`

## 判断规则

- import 如果已经进入 `domain` 或核心 service，通常是边界警报。
- 如果“没装依赖就起不来”，通常已经接近硬依赖化。
- 如果核心接口暴露了可选依赖专属概念，说明边界开始泄漏。
- 如果降级路径存在但没人验证，也应视为风险，而不是默认没问题。

## 仓库专属提醒

- `mempalace`、`chromadb`、`pypdf` 默认不是核心常驻依赖
- `services/core` 核心常驻依赖应继续收敛在 `fastapi`、`pydantic`、`httpx`
- 可选能力应优先封装在 repository、adapter 或边缘模块之后

## 强约束

- 不要把“体验更完整”当成把可选依赖变硬依赖的理由。
- 不要在核心模块里顺手新增可选依赖 import。
- 不要只修功能，不检查缺失依赖时的表现。
- 如果改动了边界或降级行为，要同步检查文档、测试和启动说明。
