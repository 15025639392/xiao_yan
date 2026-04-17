import { GoalsSummaryPanel } from "../components/GoalsSummaryPanel";
import { StatusPanel } from "../components/StatusPanel";
import { Panel } from "../components/ui/Panel";
import { WorldPanel } from "../components/WorldPanel";
import type { BeingState, Goal, InnerWorldState, MacConsoleBootstrapStatus } from "../lib/api";

export function OverviewPanel({
  focusGoalTitle,
  goals,
  latestActionLabel,
  mode,
  onUpdateGoalStatus,
  state,
  world,
  macConsoleStatus,
  onNavigate,
}: {
  focusGoalTitle: string | null;
  goals: Goal[];
  latestActionLabel: string | null;
  mode: BeingState["mode"];
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
  state: BeingState;
  world: InnerWorldState | null;
  macConsoleStatus?: MacConsoleBootstrapStatus | null;
  onNavigate: (route: "memory" | "persona") => void;
}) {
  const isAwake = mode === "awake";

  return (
    <div className="overview-page">
      <section className="overview-stage">
        <div className="overview-grid">
          <article className="overview-card overview-card--primary">
            <p className="overview-card__label">当前焦点</p>
            <p className="overview-card__value">{focusGoalTitle ?? "暂未锁定"}</p>
            <p className="overview-card__body">{state.current_thought ?? "现在没有新的显性想法。"}</p>
          </article>

          <article className="overview-card">
            <p className="overview-card__label">运行状态</p>
            <p className="overview-card__value">
              <span className={`status-badge status-badge--${mode}`}>{isAwake ? "运行中" : "休眠中"}</span>
            </p>
            <p className="overview-card__body">
              {isAwake ? "数字人正在自主运行，处理目标和任务。" : "数字人处于休眠状态，点击唤醒按钮启动。"}
            </p>
          </article>

          <article className="overview-card">
            <p className="overview-card__label">最近动作</p>
            <p className="overview-card__body">{latestActionLabel ?? "最近没有新的执行动作。"}</p>
          </article>
        </div>
      </section>

      <section className="inspector-grid inspector-grid--balanced">
        <div className="inspector-grid__col">
          <StatusPanel
            error={""}
            focusGoalTitle={focusGoalTitle}
            state={state}
            macConsoleStatus={macConsoleStatus}
            variant="compact"
          />
        </div>
        <div className="inspector-grid__col">
          <WorldPanel world={world} />
        </div>
      </section>

      <section className="inspector-grid inspector-grid--balanced">
        <div className="inspector-grid__col">
          <Panel icon="↗" title="辅助入口" subtitle="记忆与人格设置保留为次级入口">
            <div style={{ display: "grid", gap: "var(--space-3)" }}>
              <button type="button" className="app-sidebar__action-btn" onClick={() => onNavigate("memory")}>
                打开记忆库
              </button>
              <button type="button" className="app-sidebar__action-btn" onClick={() => onNavigate("persona")}>
                打开人格设置
              </button>
            </div>
          </Panel>
        </div>
      </section>

      <section className="mission-board">
        <GoalsSummaryPanel goals={goals} onUpdateGoalStatus={onUpdateGoalStatus} />
      </section>
    </div>
  );
}
