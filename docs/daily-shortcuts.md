# xiao_yan 日常快捷入口

适合项目初期高频使用的最小入口文档。

如果你只想快速开工，而不想读完整规则，先看这里。

## 1. 默认工作法

- 一次只打一条行为链
- 默认限制文件、模块或链路范围
- 默认只跑相关测试子集
- 非必要不触发重 skill
- 非必要不扫全仓

## 2. 默认请求模板

```text
目标：<一句话目标>
范围：<只允许看的文件、模块或链路>
不要做：<明确排除项>
产出：<只分析 / 直接改代码 / 只补测试 / 只出方案>
验证：<只跑哪些测试或不跑>
```

## 3. 最常用入口

- 低 token 协作规则：`docs/low-token-collaboration.md`
- 低 token 请求示例：`docs/low-token-request-examples.md`
- 项目 skill 说明：`docs/skills.md`
- 测试策略：`docs/testing-strategy.md`
- 提交前测试清单模板：`docs/test-checklist-template.md`

## 4. 常用场景建议

- 局部 bug：先用 `runtime-bug-triage`
- 局部后端改动：先用 `core-change-entrypoint`
- 大文件但只改一小块：必要时再加 `large-file-split-advisor`
- 收尾同步：用 `docs-and-tests-sync-guard`
- 项目收敛：优先用 `project-simplifier` 的轻量模式

## 5. 默认验证

按需选择，不默认全跑：

```bash
cd /Users/ldy/Desktop/work/xiao_yan/services/core && pytest <相关测试>
cd /Users/ldy/Desktop/work/xiao_yan/apps/desktop && npm test -- <相关测试>
cd /Users/ldy/Desktop/work/xiao_yan && python3 tools/check_file_budgets.py
```
