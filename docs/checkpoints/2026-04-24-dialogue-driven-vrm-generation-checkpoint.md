# 对话驱动 VRM 生成断点

## 1) 会话快照

- 任务标题：对话驱动 Blender 生成 VRM 模型
- 技能类型：需求
- 当前模式：标准
- 当前阶段：M4 生成历史恢复能力已完成，等待完整相关验证收口
- 更新时间：2026-04-24
- 负责人：项目开发者

## 2) 当前状态

- 已完成：
  - [x] 完成知识预热并确认项目边界
  - [x] 输出标准方案文档
  - [x] 选择推荐方案 A：模板参数化生成
  - [x] 完成 M0 本机预研并记录阻塞项
  - [x] 安装 Blender 4.5.0 与 VRM Add-on v3.26.7
  - [x] 使用现有 VRM 完成导入再导出烟测
  - [x] 实现最小后端生成任务 API
  - [x] 完成 fake executor 测试与真实 Blender API 烟测
  - [x] 将生成任务改为进程内后台执行，创建接口不阻塞 Blender 完成
  - [x] 增加 cancel endpoint，并验证取消会终止外部进程
  - [x] 从现有 spike VRM 生成本地可编辑 `.blend` 模板
  - [x] 验证 `.blend` 模板可重新导出 VRM
  - [x] 增加 `VRM_GENERATION_TEMPLATE_PATH` 配置
  - [x] 后端优先从 `.blend` 模板导出 VRM，并保留旧 VRM 输入路径
  - [x] 接入桌面端 `#/vrm-generation` 页面
  - [x] 支持创建任务、轮询状态、展示产物路径和取消任务
  - [x] 增加“加载为当前预览模型”的显式确认动作
  - [x] AvatarWindow 可读取本地预览模型路径并加载草稿模型
  - [x] 增加 `GET /vrm-generation/jobs?limit={limit}` 最近任务接口
  - [x] 桌面端 `形象生成` 页面挂载时展示最近生成记录
- 进行中：
  - [x] 生成历史或最近任务恢复能力已实现
- 下一步（唯一）：
  - [ ] 运行完整相关验证并收口当前阶段，后续再进入资产库/参数映射增强

## 3) 质量评分（v2 必填）

- 完整性（0-25）：25
- 可执行性（0-25）：25
- 可验收性（0-25）：25
- 风险覆盖（0-25）：23
- 总分（0-100）：98
- 当前门禁是否通过：是

## 4) 关键结论与决策

- 决策 1：推荐模板参数化生成作为 MVP 主线
  - 原因：输出可控、可回滚，符合小晏连续身份优先的方向
  - 影响：第一版依赖基础模板和资产库，不追求纯 AI 从零生成
- 决策 2：Blender 和 VRM 插件作为外部器官能力
  - 原因：避免把可选外部工具变成核心服务硬依赖
  - 影响：缺少 Blender 时核心服务必须清晰降级

## 5) 变更与证据

- 涉及文件：
  - `docs/plans/2026-04-24-dialogue-driven-vrm-generation-design.md`
  - `docs/plans/2026-04-24-dialogue-driven-vrm-generation-m0-preflight.md`
  - `docs/plans/2026-04-24-dialogue-driven-vrm-generation-m1-backend.md`
  - `docs/plans/2026-04-24-dialogue-driven-vrm-generation-m2-template.md`
  - `docs/plans/2026-04-24-dialogue-driven-vrm-generation-m3-desktop.md`
  - `docs/plans/2026-04-24-dialogue-driven-vrm-generation-m4-history.md`
  - `docs/checkpoints/2026-04-24-dialogue-driven-vrm-generation-checkpoint.md`
  - `docs/scorecards/2026-04-24-dialogue-driven-vrm-generation-scorecard.md`
  - `services/core/app/api/vrm_generation_routes.py`
  - `services/core/app/vrm_generation/models.py`
  - `services/core/app/vrm_generation/repository.py`
  - `services/core/app/vrm_generation/executor.py`
  - `services/core/app/vrm_generation/service.py`
  - `services/core/app/vrm_generation/runner.py`
  - `services/core/app/vrm_generation/runtime.py`
  - `services/core/scripts/vrm_generation/roundtrip_vrm.py`
  - `services/core/scripts/vrm_generation/prepare_blend_template.py`
  - `services/core/scripts/vrm_generation/export_blend_vrm.py`
  - `services/core/scripts/vrm_generation/character_spec.example.json`
  - `services/core/tests/test_api_vrm_generation.py`
  - `apps/desktop/src/lib/apiVrmGeneration.ts`
  - `apps/desktop/src/pages/VrmGenerationPage.tsx`
  - `apps/desktop/src/components/avatar/avatarPreviewModel.ts`
  - `apps/desktop/src/components/avatar/AvatarWindow.tsx`
  - `apps/desktop/src/styles/vrm-generation.css`
  - `apps/desktop/src/lib/appRoutes.ts`
  - `apps/desktop/src/components/app/AppMainContent.tsx`
  - `apps/desktop/src/components/app/AppSidebar.tsx`
  - `apps/desktop/src/lib/apiVrmGeneration.test.ts`
  - `apps/desktop/src/pages/VrmGenerationPage.test.tsx`
  - `apps/desktop/src/components/avatar/avatarPreviewModel.test.ts`
- 执行命令与结果：
  - `which blender` 返回 `blender not found`
  - `find /Applications -maxdepth 2 -name 'Blender*.app'` 未发现 Blender App
  - `/Applications/Blender.app/Contents/MacOS/Blender --version` 返回 Blender 4.5.0
  - VRM Add-on v3.26.7 安装成功，`import_scene.vrm` 与 `export_scene.vrm` 存在
  - `roundtrip_vrm.py` 生成 `/tmp/xiaoyan-vrm-tools/xiaoyan-script-roundtrip.vrm`
  - `cd services/core && python3 -m pytest tests/test_api_vrm_generation.py -q` 返回 `5 passed`
  - 真实 Blender API 烟测返回 `completed` 且产物 `.vrm` 存在
  - cancel 测试确认取消后外部进程不再产出 `output.vrm`
  - `prepare_blend_template.py` 生成 `services/core/.data/vrm_generation/templates/xiaoyan_base.blend`
  - `export_blend_vrm.py` 从模板导出 `/tmp/xiaoyan-vrm-tools/xiaoyan-from-template.vrm`
  - `cd services/core && python3 -m pytest tests/test_api_vrm_generation.py -q` 返回 `6 passed`
  - 真实 `VRM_GENERATION_TEMPLATE_PATH` API 烟测返回 `completed` 且产物存在
  - `cd apps/desktop && npm test -- apiVrmGeneration VrmGenerationPage avatarPreviewModel AvatarStage AppMainContent` 返回 5 个测试文件通过、7 个测试通过
  - `cd services/core && python3 -m pytest tests/test_api_vrm_generation.py::test_vrm_generation_jobs_endpoint_lists_recent_jobs -q` 返回 `1 passed`
  - `cd apps/desktop && npm test -- apiVrmGeneration VrmGenerationPage` 返回 2 个测试文件通过、5 个测试通过
  - `cd apps/desktop && npm run build` 通过，保留既有 chunk size warning
  - `python3 tools/check_file_budgets.py` 通过，只有既有大文件告警
  - `file apps/desktop/public/avatar/xiaoyan.vrm` 确认为 glTF binary model
  - `node` 解析 VRM JSON，确认 `extensionsUsed` 包含 `VRM` 且 humanoid bones 为 43
- 关键日志/截图/报告路径：
  - `docs/plans/2026-04-24-dialogue-driven-vrm-generation-design.md`
  - `docs/plans/2026-04-24-dialogue-driven-vrm-generation-m0-preflight.md`
  - `docs/plans/2026-04-24-dialogue-driven-vrm-generation-m1-backend.md`
  - `docs/plans/2026-04-24-dialogue-driven-vrm-generation-m2-template.md`
  - `docs/plans/2026-04-24-dialogue-driven-vrm-generation-m3-desktop.md`
  - `docs/plans/2026-04-24-dialogue-driven-vrm-generation-m4-history.md`

## 6) 风险与阻塞

- 风险：
  - 当前 `.blend` 模板来自 spike VRM，可编辑性和授权仍需确认
  - 当前后台任务为进程内单 worker，服务重启后只能恢复历史记录，不能恢复运行中 Blender 子进程
  - 商用授权策略未确认
- 阻塞：
  - 当前无工程阻塞；资产模板授权和商用策略仍需产品确认
- 需要谁确认：
  - 用户确认目标风格、基础模板来源、是否需要第一版前端预览

## 7) 续跑指令（下次直接用）

- 建议提示词（长版）：
  - `继续这个任务，先读取 /Users/ldy/Desktop/map/ai/docs/checkpoints/2026-04-24-dialogue-driven-vrm-generation-checkpoint.md，运行完整相关验证并收口当前阶段，后续再进入资产库/参数映射增强。`
- 若需要子agent：
  - `基于 /Users/ldy/Desktop/map/ai/docs/checkpoints/2026-04-24-dialogue-driven-vrm-generation-checkpoint.md 拆分并并行执行未完成项，回传统一格式（结论、风险、评分、下一步唯一）。`
