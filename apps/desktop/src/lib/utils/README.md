# 工具库分类

- `formatters.ts`：通用格式化工具（字节、日期时间等）
- `health.ts`：健康度相关的颜色映射等工具
- `paths.ts`：路径处理工具（拼接、回退父目录等）

统一通过 `lib/utils/index.ts` 暴露，业务组件按需导入，避免重复实现。
