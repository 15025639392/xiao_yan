# 目标链系统 设计

## 目标

让数字人的目标从离散点，演进为可连续推进的目标链。

## 第一版字段

- `chain_id`：整条目标链的公共标识
- `parent_goal_id`：直接父目标
- `generation`：当前目标在链中的代数

## 第一版规则

- 世界事件生成的首个目标是链头：`parent_goal_id=None`，`generation=0`
- 链中目标被标记为 `completed` 后，自主循环自动生成下一代目标
- 新目标继承同一 `chain_id`
- 新目标的 `parent_goal_id` 指向刚完成的目标
- 第一版只支持单链顺延，不做并行分叉
