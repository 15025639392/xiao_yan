# xiao_yan 低 Token 请求示例

本文档提供适合 `xiao_yan` 项目初期的低 token 请求示例。

目标是让后续任务默认具备：

- 范围清晰
- 排除项明确
- 产出明确
- 验证成本可控

建议配合 `docs/low-token-collaboration.md` 一起使用。

## 通用模板

```text
目标：<一句话目标>
范围：<只允许看的文件、模块或链路>
不要做：<明确排除项>
产出：<只分析 / 直接改代码 / 只补测试 / 只出方案>
验证：<只跑哪些测试或不跑>
```

## 1. 局部后端改动

```text
目标：调整 goals admission 的某个判断规则
范围：只看 services/core/app/goals/admission.py 和相关 tests
不要做：不要改 runtime_config，不要顺手拆别的模块，不要补长文档
产出：先定位最小改动点，再直接改代码
验证：只跑 services/core/tests/test_goal_admission.py
```

```text
目标：修正 chat API 的一个响应字段映射
范围：只看相关 route、response 组装逻辑和对应 tests
不要做：不要扫全仓，不要改前端，不要做架构调整
产出：直接修复并补一个回归断言
验证：只跑相关 pytest 子集
```

## 2. 局部前端改动

```text
目标：修正 Memory 页面某个 tab 切换后的请求参数
范围：只看 apps/desktop/src/pages/MemoryPage.tsx 和对应 test
不要做：不要改样式，不要重构组件层级，不要扫其他页面
产出：直接改代码并补或更新测试
验证：只跑对应 vitest 文件
```

```text
目标：修正 Capabilities 页面某个审批按钮行为
范围：只看 apps/desktop/src/pages/CapabilitiesPage.tsx 和对应 test
不要做：不要改别的页面，不要补视觉调整
产出：直接修复并验证交互请求
验证：只跑对应 vitest 文件
```

## 3. Bug 排查

```text
目标：定位 active goal 显示和 admission 实际状态不一致的问题
范围：只看相关 API、状态映射、前端展示链路和对应 tests
不要做：不要先重构，不要扫无关 goals 模块
产出：先分析根因和最小修复面，不要直接大改
验证：先不跑全量测试
```

```text
目标：定位 memory 召回异常是写入、读取还是降级路径问题
范围：只看相关 memory service、adapter、API 和对应 tests
不要做：不要扩成全仓 memory 调研，不要先补新功能
产出：先给证据点和最小修复面
验证：只跑相关 pytest 子集
```

## 4. 只补测试

```text
目标：给 goals admission 补拆分前护栏测试
范围：只看 services/core/app/goals/admission.py 和相关 tests
不要做：不要拆文件，不要改生产代码逻辑，不要补文档
产出：直接补测试并跑通过
验证：只跑 services/core/tests/test_goal_admission.py
```

```text
目标：给 Memory 页面补一个回归测试
范围：只看目标页面测试文件和必要实现
不要做：不要顺手改页面结构，不要补其他页面测试
产出：只补测试
验证：只跑目标 vitest 文件
```

## 5. 大文件拆分准备

```text
目标：判断 goals admission 这轮该不该拆，以及最小拆分点是什么
范围：只看 services/core/app/goals/admission.py、直接入口和相关 tests
不要做：不要直接全仓治理，不要顺手改 runtime_config 或 loop
产出：只出拆分建议和改动顺序
验证：先不跑全量测试
```

```text
目标：判断 chat_routes 这轮是否还能继续局部加逻辑
范围：只看 services/core/app/api/chat_routes.py、相关入口和相关 tests
不要做：不要直接开始大重构
产出：只给 keep_stable / extract_helper / extract_module 判断
验证：不跑全量测试
```

## 6. 收尾同步

```text
目标：检查这轮 goals admission 改动还缺哪些同步项
范围：只看本轮改过的文件、相关 tests、相关 docs、相关 skill 文档
不要做：不要全量扫 docs，不要清理无关历史文档
产出：只列最小同步范围、验证命令和剩余风险
验证：基于本轮实际跑过的命令写结论
```

```text
目标：检查这轮 skill 体系改动还缺哪些同步项
范围：只看 docs/skills.md、相关 project skill、README 和相关说明文档
不要做：不要扩成全仓文档治理
产出：只列需要补的同步项
验证：不用跑代码测试，只写文档检查结果
```

## 7. 轻量收敛

```text
目标：只分析某个页面是否应该留在默认主链路
范围：只看这个页面、关联 API 和直接后端路由
不要做：不要做全仓简化，不要跑全套 project-simplifier 脚本
产出：给保留 / 延后 / 删除候选结论
验证：只跑最相关的分析脚本
```

```text
目标：只分析某组 API 是否还能留在默认入口
范围：只看目标 API、调用方和直接文档
不要做：不要扩成所有 API 的统一治理
产出：给最小收敛建议
验证：按需运行相关分析脚本
```
