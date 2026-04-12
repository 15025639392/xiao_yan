import { useMemo, useState } from "react";

import type { ExecutorViewModel } from "../../lib/orchestratorWorkbench";

type StopTaskRequest = {
  sessionId: string;
  taskId: string;
  runId: string;
};

type ExecutorPanelProps = {
  executors: ExecutorViewModel[];
  onSendQuickMessage: (message: string) => Promise<void> | void;
  onStopTask: (payload: StopTaskRequest) => Promise<void> | void;
};

export function ExecutorPanel({ executors, onSendQuickMessage, onStopTask }: ExecutorPanelProps) {
  const [stopState, setStopState] = useState<Record<string, "idle" | "pending" | "success" | "fail">>({});

  const runningCount = useMemo(
    () => executors.filter((item) => item.status === "running").length,
    [executors],
  );

  if (executors.length === 0) {
    return <p className="orchestrator-empty">暂时没有执行者分配记录。</p>;
  }

  return (
    <section className="orchestrator-side-section">
      <div className="orchestrator-executor-summary" aria-label="执行者摘要">
        <span>执行者 {executors.length} 位</span>
        <strong>运行中 {runningCount}</strong>
      </div>

      <ul className="orchestrator-executor-list">
        {executors.map((executor) => {
          const key = `${executor.sessionId}:${executor.taskId}`;
          const state = stopState[key] ?? "idle";
          const canStop = executor.status === "running" && Boolean(executor.runId);
          return (
            <li key={key} className="orchestrator-executor-item">
              <div className="orchestrator-executor-item__head">
                <strong>{executor.engineerLabel}</strong>
                <span className={`orchestrator-pill orchestrator-pill--${executor.status}`}>
                  {renderTaskStatus(executor.status)}
                </span>
              </div>
              <p className="orchestrator-flow-step__summary">{executor.taskTitle}</p>
              <div className="orchestrator-inline-card__pills">
                {executor.stallLevel ? <span className="orchestrator-pill">{executor.stallLevel}</span> : null}
                {executor.runId ? <span className="orchestrator-pill">run:{executor.runId.slice(0, 8)}</span> : null}
                {executor.lastInterventionAt ? (
                  <span className="orchestrator-pill">介入:{new Date(executor.lastInterventionAt).toLocaleTimeString()}</span>
                ) : null}
              </div>

              <div className="orchestrator-inline-card__actions">
                <button
                  className="chat-page__action-btn"
                  type="button"
                  onClick={() => void onSendQuickMessage(executor.followupCommand)}
                >
                  追问卡点
                </button>
                <button
                  className="chat-page__action-btn"
                  type="button"
                  onClick={() =>
                    void onSendQuickMessage(
                      `针对${executor.engineerLabel}执行任务「${executor.taskTitle}」生成3条排障建议`,
                    )
                  }
                >
                  生成建议
                </button>
                <button
                  className="chat-page__action-btn"
                  type="button"
                  onClick={() =>
                    void onSendQuickMessage(
                      `输出主控介入摘要：执行者=${executor.engineerLabel}，任务=${executor.taskTitle}`,
                    )
                  }
                >
                  主控介入摘要
                </button>
                <button
                  className="chat-page__action-btn"
                  type="button"
                  disabled={!canStop || state === "pending" || state === "success"}
                  onClick={async () => {
                    if (!executor.runId) {
                      return;
                    }
                    setStopState((current) => ({ ...current, [key]: "pending" }));
                    try {
                      await Promise.resolve(
                        onStopTask({
                          sessionId: executor.sessionId,
                          taskId: executor.taskId,
                          runId: executor.runId,
                        }),
                      );
                      setStopState((current) => ({ ...current, [key]: "success" }));
                    } catch {
                      setStopState((current) => ({ ...current, [key]: "fail" }));
                    }
                  }}
                >
                  {state === "pending"
                    ? "停止中..."
                    : state === "success"
                      ? "已停止"
                      : state === "fail"
                        ? "停止失败"
                        : "停止任务"}
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function renderTaskStatus(status: ExecutorViewModel["status"]): string {
  if (status === "pending") return "待执行";
  if (status === "queued") return "排队中";
  if (status === "running") return "运行中";
  if (status === "succeeded") return "已完成";
  if (status === "failed") return "失败";
  return "已取消";
}
