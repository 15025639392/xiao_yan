# Goal Admission Phase 3 小流量上线与回退 Runbook

> 适用阶段：`Phase 3: Calibrated Enforce`  
> 生效范围：`services/core` 目标准入策略（`enforce` 模式）

## 1. 目标

把参数上线从“手工调参”变成“可控发布”：

- 先证据（回放）再上线（小流量）再放量（全量）
- 任意异常可在分钟级回退
- 责任边界明确，避免上线中角色不清

## 2. 角色与责任边界

| 角色 | 主要职责 | 决策权 |
|---|---|---|
| 发布 owner（工程） | 执行参数更新、观测指标、触发回滚 | 有回滚执行权 |
| 产品 owner | 判断业务反馈是否可接受 | 有放量确认权 |
| 值班（oncall） | 监控告警、故障处置、事故记录 | 有紧急降级权 |

上线前必须明确三人：发布 owner、产品 owner、oncall。

## 3. 上线前置条件（全部满足）

- 已完成本周回放对比报告（baseline vs candidate）。
- 报告文件已归档（建议：`services/core/reports/goal-admission/`）。
- 参数顺序合法：`defer_score <= min_score`（三类来源均满足）。
- 当前服务健康：`GET /health` 返回 `ok`。
- 当前模式确认：`GET /goals/admission/stats` 中 `mode=enforce`（若当前是 `shadow`，先确认发布策略）。

## 4. 推荐窗口与节奏（Asia/Shanghai）

- 小流量窗口：工作日 `10:00-12:00` 或 `14:00-16:00`。
- 观察时长：至少 `60` 分钟。
- 采样频率：每 `5` 分钟一次。
- 放量判定：连续 `3` 个采样点都满足放量条件。

## 5. 执行步骤（可直接照抄）

### 5.1 生成并归档回放证据

```bash
cd services/core
python scripts/goal_admission_replay_compare.py \
  --iterations 700 \
  --seed 20260408 \
  --candidate-min-score 0.72 \
  --candidate-defer-score 0.50 \
  --candidate-world-min-score 0.78 \
  --candidate-chain-min-score 0.66 \
  --output reports/goal-admission/replay-$(date +%F-%H%M).json
```

### 5.2 应用候选参数（进入小流量）

```bash
curl -sS -X PUT http://127.0.0.1:8000/config/goal-admission \
  -H "Content-Type: application/json" \
  -d '{
    "user_topic_min_score": 0.72,
    "user_topic_defer_score": 0.50,
    "world_event_min_score": 0.78,
    "world_event_defer_score": 0.55,
    "chain_next_min_score": 0.66,
    "chain_next_defer_score": 0.46
  }'
```

### 5.3 采样观察（5 分钟一次）

```bash
mkdir -p reports/goal-admission/canary
for i in {1..12}; do
  ts=$(date +%F-%H%M%S)
  curl -sS http://127.0.0.1:8000/goals/admission/stats \
    > "reports/goal-admission/canary/stats-${ts}.json"
  sleep 300
done
```

### 5.4 自动汇总并给出建议

```bash
python scripts/goal_admission_canary_summary.py \
  --input-dir reports/goal-admission/canary \
  --baseline-drop-rate 0.10 \
  --baseline-wip-blocked-rate 0.04 \
  --output reports/goal-admission/canary-summary-$(date +%F-%H%M).json
```

说明：

- `status=promote`：可进入放量确认。
- `status=hold`：继续观察，补采样点。
- `status=rollback`：执行第 8 节回退步骤。

### 5.5 生成发布评审报告（Markdown）

```bash
python scripts/goal_admission_release_report.py \
  --replay-report reports/goal-admission/replay-2026-04-08-1000.json \
  --canary-summary reports/goal-admission/canary-summary-2026-04-08-1130.json \
  --output reports/goal-admission/release-report-$(date +%F-%H%M).md \
  --owner-engineering alice \
  --owner-product bob \
  --owner-oncall carol
```

输出会包含：

- baseline/candidate 参数对比
- replay 与 canary 的推荐结论
- 最终放量建议（可以放量 / 继续观察 / 建议回滚）
- 三方签署区（工程 / 产品 / oncall）

### 5.6 单命令总控（采样 + 汇总 + 发布报告）

先生成演练样本（可选）：

```bash
python scripts/goal_admission_mock_samples.py \
  --output-dir reports/goal-admission/mock-samples \
  --count 12 \
  --scenario healthy \
  --seed 20260408
```

```bash
python scripts/goal_admission_canary_pipeline.py \
  --replay-report reports/goal-admission/replay-2026-04-08-1000.json \
  --sample-source-dir reports/goal-admission/mock-samples \
  --sample-count 12 \
  --canary-dir reports/goal-admission/canary \
  --canary-summary-output reports/goal-admission/canary-summary-$(date +%F-%H%M).json \
  --release-report-output reports/goal-admission/release-report-$(date +%F-%H%M).md \
  --owner-engineering alice \
  --owner-product bob \
  --owner-oncall carol
```

说明：

- 有 `--sample-source-dir` 时使用本地样本（演练/回放模式）。
- 不传 `--sample-source-dir` 时会实时请求 `GET /goals/admission/stats` 采样。

## 6. 放量条件（全部满足）

基于小流量窗口内的采样结果，以下条件连续 3 个采样点成立：

- `deferred_queue_size` 无连续单边增长（允许短时波动，不允许持续爬升）。
- `today.drop / (today.admit + today.defer + today.drop)` 未出现异常跳升（相对 baseline 增幅不超过 20%）。
- `today.wip_blocked` 未出现系统性放大（相对 baseline 增幅不超过 20%）。
- 产品侧无“目标显著进不来”反馈。

满足后，产品 owner 确认放量，进入全量。

## 7. 回滚触发条件（任一命中即回滚）

- `deferred_queue_size` 连续 `3` 个采样点上升。
- `drop` 占比相对 baseline 突增超过 `30%` 并持续 `15` 分钟。
- `wip_blocked` 相对 baseline 突增超过 `30%` 并持续 `15` 分钟。
- 出现明确业务故障反馈（目标无法进入或推进明显受阻）。

## 8. 分钟级回退步骤

### 8.1 首选：回滚到上一版参数

```bash
curl -sS -X POST http://127.0.0.1:8000/config/goal-admission/rollback
```

### 8.2 兜底：切回 shadow（强制止血）

1. 在 `services/core/.env.local` 将 `GOAL_ADMISSION_MODE=shadow`。
2. 重启后端服务。
3. 再次确认：

```bash
curl -sS http://127.0.0.1:8000/goals/admission/stats
```

期望返回中 `mode` 为 `shadow`。

## 9. 上线后留痕（必须）

- 记录发布时间、发布人、参数版本（config revision）。
- 记录回放报告路径与小流量采样目录。
- 若触发回滚，记录触发条件、回滚时间、恢复时间。
- 在周会复盘中补充“指标变化 + 原因解释 + 下轮参数建议”。
