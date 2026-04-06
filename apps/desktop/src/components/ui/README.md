# UI 组件库分类

- `core`：基础结构组件（当前在 `ui/` 根目录，如 `Panel`、`EmptyState`）
- `cards`：数据卡片与信息卡片组件（如 `MetricCard`、`SurfaceCard`）
- `overlay`：覆盖层与弹窗组件（如 `BaseModal`）

后续新增可复用组件时，优先按职责放入对应目录，并通过 `ui/index.ts` 统一导出。
