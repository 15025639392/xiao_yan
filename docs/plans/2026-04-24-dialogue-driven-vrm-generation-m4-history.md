# 对话驱动 VRM 生成 M4 生成历史恢复记录

## 1. 目标

增加最小生成历史恢复能力，让用户刷新桌面页面后仍能看到最近 VRM 生成任务和可加载草稿产物入口。

## 2. 实现范围

后端新增能力：

- `GET /vrm-generation/jobs?limit={limit}`
- 返回结构：`{ "items": VrmGenerationJob[] }`
- 默认返回最近 20 条，接口限制 `1 <= limit <= 50`
- 最近排序以任务 `created_at` 倒序为准

前端新增能力：

- `listVrmGenerationJobs({ limit })`
- `VrmGenerationPage` 挂载时读取最近 5 条任务
- 页面新增 `最近生成` 区域，展示 prompt、status 和 `output_vrm_path`

## 3. 边界说明

- 历史列表只恢复已落盘任务入口，不恢复运行中 Blender 子进程。
- 历史列表不自动加载产物，也不替换正式形象。
- 当前任务状态卡仍是主动生成后的主反馈区域，历史区只承担读取和恢复入口。
- Blender 仍是外部器官能力；缺少 Blender 不影响历史列表读取。

## 4. 验收用例

- Given 已创建多个 VRM 生成任务，When 调用 `GET /vrm-generation/jobs?limit=1`，Then 返回最新创建的一条任务。
- Given 桌面端进入 `#/vrm-generation`，When 后端返回最近任务，Then 页面展示 `最近生成`、任务 prompt 和产物路径。
- Given 最近任务读取失败，When 页面挂载，Then 页面仍可创建新任务，并只显示轻量错误提示。

## 5. 验证结果

RED 验证：

```bash
cd services/core && python3 -m pytest tests/test_api_vrm_generation.py::test_vrm_generation_jobs_endpoint_lists_recent_jobs -q
cd apps/desktop && npm test -- apiVrmGeneration VrmGenerationPage
```

结果：后端返回 `405 Method Not Allowed`；前端缺少 `listVrmGenerationJobs`。

GREEN 验证：

```bash
cd services/core && python3 -m pytest tests/test_api_vrm_generation.py::test_vrm_generation_jobs_endpoint_lists_recent_jobs -q
cd apps/desktop && npm test -- apiVrmGeneration VrmGenerationPage
```

结果：后端新增测试 `1 passed`；前端目标测试 `5 passed`。

## 6. 下一步（唯一）

运行完整相关验证并收口当前阶段，后续再进入“资产库/参数映射增强”。
