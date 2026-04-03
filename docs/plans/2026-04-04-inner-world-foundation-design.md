# 内在世界第一层 设计

## 目标

让数字人的自主行为不再只受聊天和目标直接驱动，而是先经过一层持续存在的内在世界状态。

## 第一版状态

- `time_of_day`：`morning / afternoon / evening / night`
- `energy`：`low / medium / high`
- `mood`：`calm / engaged / tired`
- `focus_tension`：`low / medium / high`

## 第一版规则

- 睡眠时：`energy=low`，`mood=tired`，`focus_tension=low`
- 白天苏醒时：能量高于夜晚
- 有 `active` 目标时：`focus_tension=high`，`mood=engaged`
- 目标刚完成时：`focus_tension` 下降，`mood=calm`
- 目标被放弃时：`focus_tension` 下降，但不使用完成式情绪

## 接入点

- `WorldStateService` 负责根据时间、苏醒状态和当前焦点目标推导内在世界
- `AutonomyLoop` 在生成 `current_thought` 和主动消息时读取这层状态，改变语气
