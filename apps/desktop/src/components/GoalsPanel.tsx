import { useState } from "react";
import type { Goal, TaskExecution, TaskExecutionStats, GoalDecompositionResult } from "../lib/api";
import {
  decomposeGoal,
  fetchTaskExecutionStats,
  fetchActiveTaskExecutions,
} from "../lib/api";
import { EmptyState } from "./ui/EmptyState";
import { Panel } from "./ui/Panel";

type GoalsPanelProps = {
  goals: Goal[];
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
};

export function GoalsPanel({ goals, onUpdateGoalStatus }: GoalsPanelProps) {
  const { chainedGroups, columns } = groupGoals(goals);
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    goalId: string;
    goalTitle: string;
    action: "abandon" | "complete";
  }>({ isOpen: false, goalId: "", goalTitle: "", action: "abandon" });
  const [collapsedColumns, setCollapsedColumns] = useState<Set<string>>(new Set(["closed"]));
  const [showExecutionPanel, setShowExecutionPanel] = useState(false);
  const [executionStats, setExecutionStats] = useState<TaskExecutionStats | null>(null);
  const [activeExecutions, setActiveExecutions] = useState<TaskExecution[]>([]);
  const [decomposedGoals, setDecomposedGoals] = useState<Set<string>>(new Set());
  const [loadingDecompose, setLoadingDecompose] = useState<Set<string>>(new Set());

  function handleAbandonClick(goalId: string, goalTitle: string) {
    setConfirmModal({
      isOpen: true,
      goalId,
      goalTitle,
      action: "abandon",
    });
  }

  function handleCompleteClick(goalId: string, goalTitle: string) {
    setConfirmModal({
      isOpen: true,
      goalId,
      goalTitle,
      action: "complete",
    });
  }

  function confirmAction() {
    if (confirmModal.goalId) {
      onUpdateGoalStatus(
        confirmModal.goalId,
        confirmModal.action === "abandon" ? "abandoned" : "completed"
      );
    }
    setConfirmModal({ isOpen: false, goalId: "", goalTitle: "", action: "abandon" });
  }

  function cancelAction() {
    setConfirmModal({ isOpen: false, goalId: "", goalTitle: "", action: "abandon" });
  }

  function toggleColumn(columnId: string) {
    setCollapsedColumns((prev) => {
      const next = new Set(prev);
      if (next.has(columnId)) {
        next.delete(columnId);
      } else {
        next.add(columnId);
      }
      return next;
    });
  }

  // 加载执行统计
  async function loadExecutionStats() {
    try {
      const stats = await fetchTaskExecutionStats();
      setExecutionStats(stats);
      const executions = await fetchActiveTaskExecutions();
      setActiveExecutions(executions);
    } catch (error) {
      console.error("Failed to load execution stats:", error);
    }
  }

  // 分解目标
  async function handleDecomposeGoal(goalId: string) {
    if (loadingDecompose.has(goalId)) return;

    setLoadingDecompose((prev) => new Set([...prev, goalId]));
    try {
      const result = await decomposeGoal(goalId);
      setDecomposedGoals((prev) => new Set([...prev, goalId]));
      // TODO: 显示分解结果，更新goals列表
    } catch (error) {
      console.error("Failed to decompose goal:", error);
    } finally {
      setLoadingDecompose((prev) => {
        const next = new Set(prev);
        next.delete(goalId);
        return next;
      });
    }
  }

  // 切换执行面板显示
  function toggleExecutionPanel() {
    if (!showExecutionPanel) {
      loadExecutionStats();
    }
    setShowExecutionPanel(!showExecutionPanel);
  }

  return (
    <Panel
      icon="🎯"
      title="目标看板"
      subtitle="管理和追踪所有目标"
      actions={
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <button
            className="btn btn--secondary btn--sm"
            type="button"
            onClick={toggleExecutionPanel}
            style={{ fontSize: "0.75rem" }}
          >
            {showExecutionPanel ? "📊 隐藏统计" : "📊 执行统计"}
          </button>
          <span className="status-badge status-badge--awake">{goals.length} 个目标</span>
        </div>
      }
    >
        {/* 任务执行统计面板 */}
        {showExecutionPanel && executionStats ? (
          <section style={{ marginBottom: "var(--space-5)" }}>
            <h3 style={{ margin: "0 0 var(--space-3)", fontSize: "0.875rem", fontWeight: 600 }}>任务执行统计</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-3)" }}>
              <StatCard label="总任务数" value={executionStats.total_tasks} />
              <StatCard label="已完成" value={executionStats.completed} color="success" />
              <StatCard label="失败" value={executionStats.failed} color="danger" />
              <StatCard label="活跃中" value={executionStats.active} color="info" />
              <StatCard
                label="成功率"
                value={`${executionStats.success_rate.toFixed(1)}%`}
                color={executionStats.success_rate >= 80 ? "success" : executionStats.success_rate >= 50 ? "warning" : "danger"}
              />
            </div>

            {activeExecutions.length > 0 && (
              <div style={{ marginTop: "var(--space-4)" }}>
                <h4 style={{ margin: "0 0 var(--space-2)", fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                  活跃任务 ({activeExecutions.length})
                </h4>
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                  {activeExecutions.map((exec) => (
                    <ExecutionCard key={exec.goal_id} execution={exec} allGoals={goals} />
                  ))}
                </div>
              </div>
            )}
          </section>
        ) : null}

        {goals.length === 0 ? (
          <EmptyState size="small">
            <p>还没有目标。</p>
          </EmptyState>
        ) : null}

        {chainedGroups.length > 0 ? (
          <section style={{ marginBottom: "var(--space-6)" }}>
            <h3 style={{ margin: "0 0 var(--space-4)", fontSize: "0.875rem", color: "var(--text-secondary)" }}>
              目标链
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "var(--space-3)" }}>
              {chainedGroups.map((group) => (
                <article
                  key={group.chainId}
                  style={{
                    padding: "var(--space-4)",
                    background: "var(--bg-surface-elevated)",
                    border: "1px solid var(--border-default)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <h4 style={{ margin: "0 0 var(--space-2)", fontSize: "0.9375rem" }}>
                    链路 {group.chainId}
                  </h4>
                  <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--text-tertiary)", lineHeight: 1.5 }}>
                    {group.summary}
                  </p>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        <section className="goal-board">
          {/* Top Row: Active (2/3) + Paused (1/3) */}
          <div className="goal-board__row">
            {columns.filter(col => col.id === "active" || col.id === "paused").map((column) => {
              const isCollapsed = collapsedColumns.has(column.id);
              const isActiveColumn = column.id === "active";
              return (
                <section
                  key={column.id}
                  className={`goal-column ${isCollapsed ? "goal-column--collapsed" : ""} ${isActiveColumn ? "goal-column--wide" : "goal-column--narrow"}`}
                >
                  <button
                    className="goal-column__header"
                    onClick={() => toggleColumn(column.id)}
                    type="button"
                    title={isCollapsed ? "展开" : "折叠"}
                  >
                    <h3 className="goal-column__title">{column.title}</h3>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <span className="goal-column__count">{column.goals.length}</span>
                      <span className="goal-column__toggle">{isCollapsed ? "▸" : "▾"}</span>
                    </div>
                  </button>

                  {!isCollapsed && (
                    <>
                      {column.goals.length === 0 ? (
                        <EmptyState size="small">
                          <p style={{ fontSize: "0.8125rem" }}>{column.description}</p>
                        </EmptyState>
                      ) : (
                        <ul className="goal-list">
                          {column.goals.map((goal) => (
                            <GoalItem
                              key={goal.id}
                              goal={goal}
                              allGoals={goals}
                              onAbandonClick={handleAbandonClick}
                              onCompleteClick={handleCompleteClick}
                              onUpdateGoalStatus={onUpdateGoalStatus}
                              onDecomposeGoal={handleDecomposeGoal}
                              loadingDecompose={loadingDecompose}
                            />
                          ))}
                        </ul>
                      )}
                    </>
                  )}
                </section>
              );
            })}
          </div>

          {/* Bottom Row: Closed (full width, default collapsed) */}
          {(() => {
            const closedColumn = columns.find(col => col.id === "closed");
            if (!closedColumn) return null;
            const isCollapsed = collapsedColumns.has("closed");
            return (
              <section className={`goal-column goal-column--full ${isCollapsed ? "goal-column--collapsed" : ""}`}>
                <button
                  className="goal-column__header"
                  onClick={() => toggleColumn("closed")}
                  type="button"
                  title={isCollapsed ? "展开" : "折叠"}
                >
                  <h3 className="goal-column__title">{closedColumn.title}</h3>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <span className="goal-column__count">{closedColumn.goals.length}</span>
                    <span className="goal-column__toggle">{isCollapsed ? "▸" : "▾"}</span>
                  </div>
                </button>

                {!isCollapsed && (
                  <>
                    {closedColumn.goals.length === 0 ? (
                      <EmptyState size="small">
                        <p style={{ fontSize: "0.8125rem" }}>{closedColumn.description}</p>
                      </EmptyState>
                    ) : (
                      <ul className="goal-list goal-list--horizontal">
                        {closedColumn.goals.map((goal) => (
                          <GoalItem
                            key={goal.id}
                            goal={goal}
                            allGoals={goals}
                            onAbandonClick={handleAbandonClick}
                            onCompleteClick={handleCompleteClick}
                            onUpdateGoalStatus={onUpdateGoalStatus}
                            onDecomposeGoal={handleDecomposeGoal}
                            loadingDecompose={loadingDecompose}
                          />
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </section>
            );
          })()}
        </section>

      {/* Confirmation Modal */}
      {confirmModal.isOpen && (
        <div className="modal-overlay" onClick={cancelAction}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal__header">
              <h3 className="modal__title">
                {confirmModal.action === "abandon" ? "确认放弃目标" : "确认完成目标"}
              </h3>
            </div>
            <div className="modal__body">
              <p>
                {confirmModal.action === "abandon"
                  ? `确定要放弃目标 "${confirmModal.goalTitle}" 吗？此操作不可撤销。`
                  : `确定要完成目标 "${confirmModal.goalTitle}" 吗？`}
              </p>
            </div>
            <div className="modal__footer">
              <button className="btn btn--secondary" onClick={cancelAction} type="button">
                取消
              </button>
              <button
                className={`btn ${confirmModal.action === "abandon" ? "btn--danger" : "btn--primary"}`}
                onClick={confirmAction}
                type="button"
              >
                {confirmModal.action === "abandon" ? "确认放弃" : "确认完成"}
              </button>
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}

type GoalItemProps = {
  goal: Goal;
  allGoals: Goal[];
  onAbandonClick: (goalId: string, goalTitle: string) => void;
  onCompleteClick: (goalId: string, goalTitle: string) => void;
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
  onDecomposeGoal: (goalId: string) => void;
  loadingDecompose: Set<string>;
};

function GoalItem({ goal, allGoals, onAbandonClick, onCompleteClick, onUpdateGoalStatus, onDecomposeGoal, loadingDecompose }: GoalItemProps) {
  const [isDecomposed, setIsDecomposed] = useState(false);

  return (
    <li className="goal-card">
      <div className="goal-card__top">
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="goal-card__title" title={goal.title}>{goal.title}</p>
          <div className="goal-card__meta">
            {goal.chain_id ? (
              <span className="goal-card__meta-item">链 {goal.chain_id}</span>
            ) : null}
            <span className="goal-card__meta-item">G{goal.generation ?? 0}</span>
            {goal.source ? (
              <span className="goal-card__meta-item" title={goal.source}>📌</span>
            ) : null}
          </div>
        </div>
        <span className={`status-badge status-badge--${goal.status}`}>
          {renderGoalStatus(goal.status)}
        </span>
      </div>

      {/* 目标详情区域 */}
      {(goal.generation === 0 && goal.status === "active") && (
        <div style={{ marginTop: "var(--space-2)", paddingTop: "var(--space-2)", borderTop: "1px solid var(--border-default)" }}>
          <button
            className="btn btn--secondary btn--sm"
            type="button"
            onClick={() => onDecomposeGoal(goal.id)}
            disabled={loadingDecompose.has(goal.id)}
            style={{ fontSize: "0.75rem", padding: "var(--space-1) var(--space-2)" }}
          >
            {loadingDecompose.has(goal.id) ? "⏳ 分解中..." : "🔧 分解任务"}
          </button>
        </div>
      )}

      {goal.status !== "completed" && goal.status !== "abandoned" ? (
        <div className="goal-card__actions">
          {goal.status === "active" ? (
            <button
              className="btn btn--secondary btn--sm"
              type="button"
              onClick={() => onUpdateGoalStatus(goal.id, "paused")}
            >
              暂停
            </button>
          ) : null}

          {goal.status === "paused" ? (
            <button
              className="btn btn--secondary btn--sm"
              type="button"
              onClick={() => onUpdateGoalStatus(goal.id, "active")}
            >
              恢复
            </button>
          ) : null}

          <button
            className="btn btn--primary btn--sm"
            type="button"
            onClick={() => onCompleteClick(goal.id, goal.title)}
          >
            完成
          </button>

          <button
            className="btn btn--danger btn--sm"
            type="button"
            onClick={() => onAbandonClick(goal.id, goal.title)}
          >
            放弃
          </button>
        </div>
      ) : null}
    </li>
  );
}

function renderGoalStatus(status: Goal["status"]): string {
  switch (status) {
    case "active":
      return "推进中";
    case "paused":
      return "已暂停";
    case "completed":
      return "已完成";
    case "abandoned":
      return "已放弃";
  }
}

function groupGoals(goals: Goal[]): {
  chainedGroups: Array<{ chainId: string; goals: Goal[]; summary: string }>;
  columns: Array<{ id: string; title: string; description: string; goals: Goal[] }>;
} {
  const chainedMap = new Map<string, Goal[]>();

  goals.forEach((goal) => {
    if (goal.chain_id) {
      const existing = chainedMap.get(goal.chain_id) ?? [];
      existing.push(goal);
      chainedMap.set(goal.chain_id, existing);
    }
  });

  const chainedGroups = Array.from(chainedMap.entries()).map(([chainId, chainGoals]) => {
    const sortedGoals = sortGoalsByGeneration(chainGoals);

    return {
      chainId,
      goals: sortedGoals,
      summary: summarizeChain(sortedGoals),
    };
  });

  const columns = [
    {
      id: "active",
      title: "当前推进",
      description: "正在积极进行的目标。",
      goals: goals.filter((goal) => goal.status === "active"),
    },
    {
      id: "paused",
      title: "等待恢复",
      description: "已暂停但可随时恢复的目标。",
      goals: goals.filter((goal) => goal.status === "paused"),
    },
    {
      id: "closed",
      title: "已收束",
      description: "已完成或已放弃的目标。",
      goals: goals.filter(
        (goal) => goal.status === "completed" || goal.status === "abandoned",
      ),
    },
  ];

  return { chainedGroups, columns };
}

function sortGoalsByGeneration(goals: Goal[]): Goal[] {
  return [...goals].sort((left, right) => (left.generation ?? 0) - (right.generation ?? 0));
}

function summarizeChain(goals: Goal[]): string {
  const currentGoal = findCurrentGoal(goals);
  const currentGeneration = currentGoal?.generation ?? 0;
  const currentStatus = currentGoal?.status ?? "active";
  const currentTitle = currentGoal?.title ?? "未知目标";

  return `共 ${goals.length} 步，当前第 ${currentGeneration} 代，${renderGoalStatus(currentStatus)}，"${currentTitle}"`;
}

function findCurrentGoal(goals: Goal[]): Goal | undefined {
  const highestGeneration = Math.max(...goals.map((goal) => goal.generation ?? 0));
  const latestGenerationGoals = goals.filter(
    (goal) => (goal.generation ?? 0) === highestGeneration,
  );

  return [...latestGenerationGoals].sort(
    (left, right) => getStatusPriority(left.status) - getStatusPriority(right.status),
  )[0];
}

function getStatusPriority(status: Goal["status"]): number {
  switch (status) {
    case "active":
      return 0;
    case "paused":
      return 1;
    case "completed":
      return 2;
    case "abandoned":
      return 3;
  }
}

// ══════════════════════════════════════════════
// 辅助组件
// ══════════════════════════════════════════════

function StatCard({ label, value, color = "default" }: { label: string; value: number | string; color?: string }) {
  const colorVar = color === "success" ? "var(--success)" : color === "danger" ? "var(--danger)" : color === "warning" ? "var(--warning)" : color === "info" ? "var(--info)" : "var(--text-primary)";
  return (
    <div style={{
      padding: "var(--space-3)",
      background: "var(--bg-surface-elevated)",
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--border-default)",
    }}>
      <div style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", marginBottom: "var(--space-1)" }}>{label}</div>
      <div style={{ fontSize: "1.5rem", fontWeight: 600, color: colorVar }}>{value}</div>
    </div>
  );
}

function ExecutionCard({ execution, allGoals }: { execution: TaskExecution; allGoals: Goal[] }) {
  const goal = allGoals.find((g) => g.id === execution.goal_id);

  return (
    <div style={{
      padding: "var(--space-3)",
      background: "var(--bg-surface-elevated)",
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--border-default)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
        <span style={{ fontSize: "0.875rem", fontWeight: 500 }}>{goal?.title || execution.goal_id}</span>
        <span className="intensity-badge" style={{ fontSize: "0.75rem", padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius-full)" }}>
          {(execution.progress * 100).toFixed(0)}%
        </span>
      </div>
      <div style={{ marginBottom: "var(--space-2)" }}>
        <div style={{
          height: "4px",
          background: "var(--bg-surface)",
          borderRadius: "var(--radius-full)",
          overflow: "hidden",
        }}>
          <div style={{
            height: "100%",
            background: execution.status === "completed" ? "var(--success)" : execution.status === "abandoned" ? "var(--danger)" : "var(--info)",
            borderRadius: "var(--radius-full)",
            transition: "width 300ms ease",
            width: `${execution.progress * 100}%`,
          }} />
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-tertiary)" }}>
        <span>{renderGoalStatus(execution.status)}</span>
        <span>{new Date(execution.started_at).toLocaleString("zh-CN")}</span>
      </div>
    </div>
  );
}
