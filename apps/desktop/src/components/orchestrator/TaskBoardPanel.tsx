import { useMemo, useState } from "react";

import type { TaskBoardViewModel } from "../../lib/orchestratorWorkbench";

type TaskBoardPanelProps = {
  viewModel: TaskBoardViewModel;
  onSendQuickMessage: (message: string) => Promise<void> | void;
};

export function TaskBoardPanel({ viewModel, onSendQuickMessage }: TaskBoardPanelProps) {
  const [showAllTasks, setShowAllTasks] = useState(false);

  if (viewModel.tasks.length === 0) {
    return <p className="orchestrator-empty">当前会话还没有任务。</p>;
  }

  const primaryTasks = useMemo(
    () => viewModel.tasks.filter((task) => task.status === "running" || task.status === "failed"),
    [viewModel.tasks],
  );
  const secondaryTaskCount = viewModel.tasks.length - primaryTasks.length;
  const visibleTasks = showAllTasks ? viewModel.tasks : primaryTasks;

  return (
    <section className="orchestrator-side-section">
      <div className="orchestrator-workbench-metrics" aria-label="任务节奏指标">
        <Metric label="运行中" value={String(viewModel.metrics.running)} />
        <Metric label="排队中" value={String(viewModel.metrics.queued)} />
        <Metric label="失败" value={String(viewModel.metrics.failed)} />
        <Metric label="卡点" value={String(viewModel.metrics.stalled)} />
        <Metric label="平均回执" value={`${viewModel.metrics.averageReceiptMinutes}m`} />
      </div>

      {!showAllTasks && primaryTasks.length === 0 ? (
        <p className="orchestrator-taskboard__hint">当前没有运行中或失败任务，已折叠其他任务。</p>
      ) : null}

      {visibleTasks.length > 0 ? (
        <ol className="orchestrator-flow-list orchestrator-flow-list--compact">
          {visibleTasks.map((task) => (
            <li key={task.taskId} className={`orchestrator-flow-step orchestrator-flow-step--${task.status}`}>
              <div className="orchestrator-flow-step__body">
                <div className="orchestrator-flow-step__head">
                  <div>
                    <div className="orchestrator-flow-step__eyebrow">{task.kind.toUpperCase()}</div>
                    <strong>{task.title}</strong>
                  </div>
                  <span className={`orchestrator-pill orchestrator-pill--${task.status}`}>{renderTaskStatus(task.status)}</span>
                </div>
                <p className="orchestrator-flow-step__summary">{task.summary}</p>
                <div className="orchestrator-inline-card__pills">
                  {task.engineerLabel ? <span className="orchestrator-pill">{task.engineerLabel}</span> : null}
                  {task.delegateRunId ? <span className="orchestrator-pill">run:{task.delegateRunId.slice(0, 8)}</span> : null}
                  {task.stallLevel ? <span className="orchestrator-pill">{task.stallLevel}</span> : null}
                </div>
                <div className="orchestrator-inline-card__actions">
                  <button
                    className="chat-page__action-btn"
                    type="button"
                    onClick={() => void onSendQuickMessage(`解释一下任务「${task.title}」当前状态与下一步`)}
                  >
                    查看回执
                  </button>
                  {task.status === "failed" ? (
                    <button
                      className="chat-page__action-btn"
                      type="button"
                      onClick={() => void onSendQuickMessage(`分析任务「${task.title}」失败原因并给修复建议`)}
                    >
                      分析失败
                    </button>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ol>
      ) : null}

      {secondaryTaskCount > 0 ? (
        <button
          className="chat-page__action-btn orchestrator-taskboard__toggle"
          type="button"
          onClick={() => setShowAllTasks((current) => !current)}
        >
          {showAllTasks ? "收起非关键任务" : `查看全部任务（${viewModel.tasks.length}）`}
        </button>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="orchestrator-workbench-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function renderTaskStatus(status: TaskBoardViewModel["tasks"][number]["status"]): string {
  if (status === "pending") return "待执行";
  if (status === "queued") return "排队中";
  if (status === "running") return "运行中";
  if (status === "succeeded") return "已完成";
  if (status === "failed") return "失败";
  return "已取消";
}
