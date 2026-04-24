# 对话驱动 VRM 生成 M3 桌面端接入记录

## 1. 目标

接入桌面端最小生成页面，让用户可以：

- 输入 VRM 形象描述 prompt。
- 创建后端生成任务。
- 轮询任务状态。
- 展示 `output_vrm_path`、`spec_path` 与错误信息。
- 取消运行中的任务。
- 用户确认后，将完成的 VRM 产物加载为当前预览模型，但不替换正式形象。

## 2. 实现范围

新增前端 API：

- `apps/desktop/src/lib/apiVrmGeneration.ts`

新增页面：

- `apps/desktop/src/pages/VrmGenerationPage.tsx`
- `apps/desktop/src/styles/vrm-generation.css`
- `apps/desktop/src/components/avatar/avatarPreviewModel.ts`

接入路由与导航：

- `apps/desktop/src/lib/appRoutes.ts`
- `apps/desktop/src/components/app/AppMainContent.tsx`
- `apps/desktop/src/components/app/AppSidebar.tsx`
- `apps/desktop/src/styles/workbench.css`

新增测试：

- `apps/desktop/src/lib/apiVrmGeneration.test.ts`
- `apps/desktop/src/pages/VrmGenerationPage.test.tsx`
- 更新 `apps/desktop/src/components/app/AppMainContent.test.tsx`

## 3. 页面行为

- 新增导航项：`形象生成`。
- 新增 hash 路由：`#/vrm-generation`。
- 页面默认提示词：`小晏，温柔，浅棕短发，蓝眼睛，白色居家裙`。
- 点击 `生成 VRM 草稿` 后调用 `POST /vrm-generation/jobs`。
- 任务未到终态时定时调用 `GET /vrm-generation/jobs/{job_id}`。
- 终态包括：`completed`、`failed`、`cancelled`。
- 点击 `取消任务` 后调用 `POST /vrm-generation/jobs/{job_id}/cancel`。
- 任务 `completed` 且有 `output_vrm_path` 时显示 `加载为当前预览模型`。
- 点击加载预览后，将产物路径存入本地预览偏好并重新打开 VRM 外显窗口。
- 预览窗口启动时读取本地预览路径，并通过 Tauri `convertFileSrc` 转为可加载 URL。

## 4. UX 边界

- 当前页面只展示本地文件路径，不内嵌 3D 预览。
- 当前产物明确标注为草稿，不自动替换正式形象。
- 加载预览动作是显式确认，不修改 persona 的正式形象配置。
- 表单有显式 label、可键盘提交、按钮有 disabled 状态。
- 页面使用既有 CSS token，不引入新 UI 依赖。

## 5. 验证结果

前端目标测试：

```bash
cd apps/desktop && npm test -- apiVrmGeneration VrmGenerationPage AppMainContent
```

结果：`5 passed`，共 `7 passed`。

前端构建：

```bash
cd apps/desktop && npm run build
```

结果：通过。构建仍提示部分 chunk 超过 500KB，主要来自既有 VRM/Three 运行时体积，非本页面新增阻塞。

后端目标测试：

```bash
cd services/core && python3 -m pytest tests/test_api_vrm_generation.py -q
```

结果：`6 passed`。

文件体积检查：

```bash
python3 tools/check_file_budgets.py
```

结果：通过；仍提示 3 个既有大文件告警，非本次新增。

## 6. 下一步（唯一）

增加生成历史列表或最近一次任务恢复，避免刷新页面后丢失刚生成的草稿入口。
