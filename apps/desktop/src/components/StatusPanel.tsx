import { useState, useEffect } from "react";
import type {
  BeingState,
  SelfImprovementEdit,
  SelfImprovementJob,
} from "../lib/api";
import { rollbackSelfImprovementJob } from "../lib/api";
import { ApprovalPanel } from "./ApprovalPanel";
import { PersonaCard } from "./PersonaCard";
import { MemoryPanel } from "./MemoryPanel";

type StatusPanelProps = {
  state: BeingState;
  error: string;
  focusGoalTitle?: string | null;
  onRollback?: (jobId: string) => void;
  onApprovalDecision?: (jobId: string, approved: boolean) => void;
};

export function StatusPanel({ state, error, focusGoalTitle, onRollback, onApprovalDecision }: StatusPanelProps) {
  const planCompleted =
    state.today_plan?.steps.length &&
    state.today_plan.steps.every((step) => step.status === "completed");
  const selfImprovementJob = state.self_improvement_job;

  return (
    <section className="panel">
      <div className="panel__header">
        <div className="panel__title-group">
          <div className="panel__icon">📊</div>
          <div>
            <h2 className="panel__title">当前状态</h2>
            <p className="panel__subtitle">系统实时读数</p>
          </div>
        </div>
        <span className={`status-badge status-badge--${state.mode}`}>
          {renderModeLabel(state.mode)}
        </span>
      </div>

      <div className="panel__content">
        {/* Phase 7: 人格卡片 */}
        <PersonaCard style={{ marginBottom: "var(--space-4)" }} />

        {/* Phase 8: 记忆面板 */}
        <MemoryPanel style={{ marginBottom: "var(--space-4)" }} />

        <div className="metric-grid">
          <div className="metric-card">
            <p className="metric-card__label">运行状态</p>
            <p className="metric-card__value">{renderModeLabel(state.mode)}</p>
          </div>
          <div className="metric-card">
            <p className="metric-card__label">当前阶段</p>
            <p className="metric-card__value">{renderFocusMode(state.focus_mode)}</p>
          </div>
        </div>

        {focusGoalTitle ? (
          <div className="metric-card" style={{ marginTop: "var(--space-3)" }}>
            <p className="metric-card__label">当前专注目标</p>
            <p className="metric-card__value">{focusGoalTitle}</p>
          </div>
        ) : null}

        {state.last_action ? (
          <div className="metric-card" style={{ marginTop: "var(--space-3)" }}>
            <p className="metric-card__label">最近动作</p>
            <p className="metric-card__value">
              {state.last_action.command} → {state.last_action.output}
            </p>
          </div>
        ) : null}

        <div className="metric-card" style={{ marginTop: "var(--space-3)" }}>
          <p className="metric-card__label">当前想法</p>
          <p className="metric-card__value">{state.current_thought ?? "还没有浮现新的念头。"}</p>
        </div>

        {/* ── 今日计划（保持原逻辑）── */}
        {state.today_plan ? (
          <section style={{ marginTop: "var(--space-5)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-3)" }}>
              <h3 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600 }}>今日计划</h3>
              {planCompleted ? <span className="status-badge status-badge--completed">已完成</span> : null}
            </div>
            <p style={{ margin: "0 0 var(--space-3)", color: "var(--text-secondary)", fontSize: "0.875rem" }}>
              {state.today_plan.goal_title}
            </p>
            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              {state.today_plan.steps.map((step) => (
                <li
                  key={step.content}
                  style={{
                    display: "flex",
                    gap: "var(--space-3)",
                    alignItems: "flex-start",
                    padding: "var(--space-3)",
                    background: "var(--bg-surface-elevated)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <span
                    style={{
                      padding: "var(--space-1) var(--space-2)",
                      background: step.status === "completed" ? "var(--success-muted)" : "var(--warning-muted)",
                      color: step.status === "completed" ? "var(--success)" : "var(--warning)",
                      borderRadius: "var(--radius-full)",
                      fontSize: "0.75rem",
                      fontWeight: 500,
                      flexShrink: 0,
                    }}
                  >
                    {step.status === "completed" ? "已完成" : "待处理"}
                  </span>
                  <div>
                    <p style={{ margin: 0, fontSize: "0.875rem" }}>{step.content}</p>
                    {step.kind === "action" && step.command ? (
                      <p style={{ margin: "var(--space-1) 0 0", fontSize: "0.75rem", color: "var(--text-tertiary)", fontFamily: "monospace" }}>
                        {step.command}
                      </p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {/* ═══════════════════════════════════════
            🧬 自编程面板 — Phase 1~6 全量展示
           ═══════════════════════════════════════ */}
        {selfImprovementJob ? (
          selfImprovementJob.status === "pending_approval" ? (
            <ApprovalPanel
              job={selfImprovementJob}
              onDecision={(jobId, approved) => {
                onApprovalDecision?.(jobId, approved);
              }}
            />
          ) : (
            <SelfImprovementPanel job={selfImprovementJob} onRollback={onRollback} />
          )
        ) : null}

        {error ? (
          <div style={{ marginTop: "var(--space-4)", padding: "var(--space-3)", background: "var(--danger-muted)", borderRadius: "var(--radius-md)", color: "var(--danger)", fontSize: "0.875rem" }}>
            {error}
          </div>
        ) : null}
      </div>
    </section>
  );
}

// ══════════════════════════════════════════════
// 🧬 自编程面板组件
// ══════════════════════════════════════════════

function SelfImprovementPanel({
  job,
  onRollback,
}: {
  job: NonNullable<BeingState["self_improvement_job"]>;
  onRollback?: (jobId: string) => void;
}) {
  const [showDiff, setShowDiff] = useState(false);
  const [showDetails, setShowDetails] = useState(true); // 默认展开详情
  const [rollingBack, setRollingBack] = useState(false);
  const [rollbackOk, setRollbackOk] = useState<string | null>(null);
  const [rollbackErr, setRollbackErr] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false); // 确认弹窗

  // 判断是否可以回滚：已生效 + 有快照
  const canRollback = job.status === "applied" && !!job.snapshot_taken;
  const edits = job.edits ?? [];
  const hasHealthData = job.health_score != null;

  function openConfirmDialog() {
    setShowConfirm(true);
  }

  function closeConfirmDialog() {
    setShowConfirm(false);
  }

  async function executeRollback() {
    if (!canRollback) return;
    closeConfirmDialog();
    setRollingBack(true);
    setRollbackOk(null);
    setRollbackErr(null);

    try {
      const result = await rollbackSelfImprovementJob(job.id, "用户手动触发回滚");
      setRollbackOk(result.message ?? "回滚成功");
      onRollback?.(job.id);
    } catch (e) {
      setRollbackErr(e instanceof Error ? e.message : "回滚失败");
    } finally {
      setRollingBack(false);
    }
  }

  return (
    <section className="si-panel" style={{ marginTop: "var(--space-5)" }}>
      {/* 头部：标题 + 状态 badge */}
      <div className="si-panel__header" onClick={() => setShowDetails(!showDetails)} style={{ cursor: "pointer" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <span className="si-panel__icon">🧬</span>
          <h3 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600 }}>自编程系统</h3>
          {job.candidate_label ? (
            <span className="si-badge si-badge--candidate">{job.candidate_label}</span>
          ) : null}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          {/* 健康度圆环（Phase 5） */}
          {hasHealthData ? (
            <HealthRing score={job.health_score!} grade={job.health_grade!} />
          ) : null}
          <span className={`status-badge status-badge--${siStatusClass(job.status)}`}>
            {renderSelfImprovementStatus(job.status)}
          </span>
          <svg
            className="si-chevron"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            width="16"
            height="16"
            style={{
              transform: showDetails ? "rotate(180deg)" : "rotate(0)",
              transition: "transform 200ms ease",
            }}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </div>

      {showDetails ? (
        <div className="si-panel__body">
          {/* 基础信息行 */}
          <div className="si-grid">
            <div className="si-field">
              <span className="si-field__label">目标区域</span>
              <span className="si-field__value">{job.target_area}</span>
            </div>
            <div className="si-field">
              <span className="si-field__label">阶段</span>
              <span className="si-field__value si-field__value--phase">{renderSelfImprovementStatus(job.status)}</span>
            </div>
          </div>

          {/* 原因 & 方案 */}
          <div className="si-section">
            <div className="si-section__row">
              <div className="si-section__col">
                <h4 className="si-section__title">原因</h4>
                <p className="si-section__text">{job.reason}</p>
              </div>
              <div className="si-section__col">
                <h4 className="si-section__title">方案</h4>
                <p className="si-section__text">{job.spec}</p>
              </div>
            </div>
          </div>

          {/* 补丁摘要 */}
          {job.patch_summary ? (
            <div className="si-section">
              <h4 className="si-section__title">补丁摘要</h4>
              <p className="si-section__text si-text--mono">{job.patch_summary}</p>
            </div>
          ) : null}

          {/* 触碰文件列表（Phase 1+） */}
          {job.touched_files && job.touched_files.length > 0 ? (
            <div className="si-section">
              <h4 className="si-section__title">触碰文件</h4>
              <div className="si-file-list">
                {job.touched_files.map((fp) => (
                  <span key={fp} className="si-file-tag">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-8V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    {fp}
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          {/* Git 信息（Phase 3） */}
          {(job.branch_name || job.commit_hash || job.commit_message) ? (
            <div className="si-section si-section--git">
              <h4 className="si-section__title si-section__title--icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/></svg>
                Git 工作流
              </h4>
              <div className="si-git-info">
                {job.branch_name ? (
                  <div className="si-git-row">
                    <span className="si-git-label">分支</span>
                    <code className="si-git-value">{job.branch_name}</code>
                  </div>
                ) : null}
                {job.commit_hash ? (
                  <div className="si-git-row">
                    <span className="si-git-label">Commit</span>
                    <code className="si-git-value">{job.commit_hash.slice(0, 8)}</code>
                  </div>
                ) : null}
                {job.commit_message ? (
                  <div className="si-git-row si-git-row--full">
                    <span className="si-git-label">Message</span>
                    <code className="si-git-value">{job.commit_message}</code>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}

          {/* 沙箱 / 冲突检测（Phase 4） */}
          {job.sandbox_prechecked || job.conflict_severity !== "safe" ? (
            <div className="si-section">
              <h4 className="si-section__title si-section__title--icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                安全检查
              </h4>
              <div className="si-safety-grid">
                {job.sandbox_prechecked ? (
                  <div className={`si-safety-item ${job.sandbox_result ? "si-safety-item--ok" : ""}`}>
                    <span className="si-safety-icon">🛡️</span>
                    <div>
                      <span className="si-safety-label">沙箱预检</span>
                      <span className="si-safety-detail">{job.sandbox_result ?? "通过"}</span>
                    </div>
                  </div>
                ) : null}
                <div className={`si-safety-item si-safety-item--${job.conflict_severity ?? "safe"}`}>
                  <span className="si-safety-icon">{conflictIcon(job.conflict_severity ?? "safe")}</span>
                  <div>
                    <span className="si-safety-label">冲突检测</span>
                    <span className="si-safety-detail">{conflictLabel(job.conflict_severity ?? "safe")}</span>
                  </div>
                </div>
              </div>
              {job.conflict_details ? (
                <p className="si-conflict-detail">{job.conflict_details}</p>
              ) : null}
            </div>
          ) : null}

          {/* Diff 详情 — 可折叠 */}
          {edits.length > 0 ? (
            <div className="si-section">
              <button
                type="button"
                className="si-diff-toggle"
                onClick={() => setShowDiff(!showDiff)}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  {showDiff ? <polyline points="18 15 12 9 6 15" /> : <polyline points="6 9 12 15 18 9" />}
                </svg>
                <span>代码变更 ({edits.length} 个编辑)</span>
                <span className="si-diff-count">{edits.length}</span>
              </button>
              {showDiff ? (
                <div className="si-diff-list">
                  {edits.map((edit, idx) => (
                    <DiffViewer key={`${edit.file_path}-${idx}`} edit={edit} index={idx} />
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {/* 回滚操作区（Phase 5） */}
          {canRollback || job.rollback_info ? (
            <div className="si-section si-section--rollback">
              {job.rollback_info ? (
                <div className="si-rollback-banner si-rollback-banner--info">
                  <span>🔄</span>
                  <span>{job.rollback_info}</span>
                </div>
              ) : null}
              {canRollback ? (
                <>
                  <h4 className="si-section__title">回滚操作</h4>
                  <p className="si-rollback-hint">此操作将恢复到修改前的文件状态（快照已保存）</p>
                  <div className="si-rollback-actions">
                    <button
                      type="button"
                      className="btn btn--danger btn--sm"
                      disabled={rollingBack}
                      onClick={() => openConfirmDialog()}
                    >
                      {rollingBack ? "⏳ 回滚中..." : "↩️ 执行回滚"}
                    </button>
                  </div>
                  {rollbackOk ? (
                    <div className="si-rollback-banner si-rollback-banner--success">{rollbackOk}</div>
                  ) : null}
                  {rollbackErr ? (
                    <div className="si-rollback-banner si-rollback-banner--error">{rollbackErr}</div>
                  ) : null}
                </>
              ) : null}
            </div>
          ) : null}

          {/* 冷却倒计时 */}
          {job.cooldown_until ? (
            <CooldownTimer until={job.cooldown_until} />
          ) : null}
        </div>
      ) : null}

      {/* ═══ 确认回滚弹窗 ═══ */}
      {showConfirm ? (
        <div className="modal-overlay" onClick={closeConfirmDialog}>
          <div
            className="modal modal--danger"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
          >
            <div className="modal__header">
              <h3 className="modal__title">⚠️ 确认回滚</h3>
            </div>
            <div className="modal__body">
              <p style={{ margin: "0 0 var(--space-3)" }}>
                此操作将撤销自编程对以下文件的修改，恢复到修改前的状态：
              </p>
              <ul style={{ margin: 0, paddingLeft: "20px", color: "var(--text-secondary)" }}>
                {(job.touched_files ?? []).map((f) => (
                  <li key={f}><code>{f}</code></li>
                ))}
              </ul>
              <p style={{ margin: "var(--space-4) 0 0", color: "var(--danger)", fontWeight: 500 }}>
                ⚠️ 此操作不可自动重做。请确认要回滚吗？
              </p>
            </div>
            <div className="modal__footer">
              <button
                type="button"
                className="btn btn--sm"
                onClick={closeConfirmDialog}
                disabled={rollingBack}
              >
                取消
              </button>
              <button
                type="button"
                className="btn btn--danger btn--sm"
                onClick={() => executeRollback()}
                autoFocus
              >
                {rollingBack ? "⏳ 执行中..." : "确认回滚"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

// ══════════════════════════════════════════════
// 子组件：Diff 查看器
// ══════════════════════════════════════════════

function DiffViewer({ edit, index }: { edit: SelfImprovementEdit; index: number }) {
  const [expanded, setExpanded] = useState(false);

  if (edit.kind === "create") {
    return (
      <div className="si-diff-block">
        <div className="si-diff-header" onClick={() => setExpanded(!expanded)}>
          <span className="si-diff-kind si-diff-kind--create">CREATE</span>
          <code className="si-diff-path">{edit.file_path}</code>
          <svg className="si-diff-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ transform: expanded ? "rotate(180deg)" : "none" }}>
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
        {expanded ? (
          <pre className="si-diff-content si-diff-content--new">
            <code>{(edit.file_content ?? "").slice(0, 2000)}{(edit.file_content?.length ?? 0) > 2000 ? "\n... (截断)" : ""}</code>
          </pre>
        ) : null}
      </div>
    );
  }

  if (edit.kind === "insert") {
    return (
      <div className="si-diff-block">
        <div className="si-diff-header" onClick={() => setExpanded(!expanded)}>
          <span className="si-diff-kind si-diff-kind--insert">INSERT</span>
          <code className="si-diff-path">{edit.file_path}</code>
        </div>
        {expanded ? (
          <div className="si-diff-content-wrapper">
            <pre className="si-diff-content si-diff-content--context">
              <code>... {edit.insert_after ?? "..."} ...</code>
            </pre>
            <pre className="si-diff-content si-diff-content--new">
              <code>+ {(edit.replace_text ?? "").slice(0, 1000)}</code>
            </pre>
          </div>
        ) : null}
      </div>
    );
  }

  // REPLACE（最常见）
  return (
    <div className="si-diff-block">
      <div className="si-diff-header" onClick={() => setExpanded(!expanded)}>
        <span className="si-diff-kind si-diff-kind--replace">REPLACE</span>
        <code className="si-diff-path">{edit.file_path}</code>
        <svg className="si-diff-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ transform: expanded ? "rotate(180deg)" : "none" }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
      {expanded ? (
        <div className="si-diff-content-wrapper">
          <pre className="si-diff-content si-diff-content--removed">
            <code>- {(edit.search_text ?? "").slice(0, 1000)}</code>
          </pre>
          <pre className="si-diff-content si-diff-content--new">
            <code>+ {(edit.replace_text ?? "").slice(0, 1000)}</code>
          </pre>
        </div>
      ) : null}
    </div>
  );
}

// ══════════════════════════════════════════════
// 子组件：健康度圆环（Phase 5）
// ══════════════════════════════════════════════

function HealthRing({ score, grade }: { score: number; grade: string }) {
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = healthColor(score);

  return (
    <div className="health-ring" title={`健康度 ${score.toFixed(0)} 分 (${grade})`}>
      <svg width="44" height="44" viewBox="0 0 44 44">
        <circle cx="22" cy="22" r={radius} fill="none" stroke="var(--border-default)" strokeWidth="4" />
        <circle
          cx="22" cy="22" r={radius}
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 22 22)"
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
      </svg>
      <span className="health-ring__score" style={{ color }}>{score.toFixed(0)}</span>
    </div>
  );
}

// ══════════════════════════════════════════════
// 子组件：冷却计时器
// ══════════════════════════════════════════════

function CooldownTimer({ until }: { until: string }) {
  const [remaining, setRemaining] = useState("");

  // 简单的剩余时间显示（不精确，靠轮询刷新即可）
  function calcRemain() {
    const diff = new Date(until).getTime() - Date.now();
    if (diff <= 0) return "";
    const min = Math.floor(diff / 60000);
    const sec = Math.floor((diff % 60000) / 1000);
    return `${min}:${sec.toString().padStart(2, "0")}`;
  }

  // 用 setInterval 每秒更新（组件卸载时清理）
  useState(() => {
    const id = setInterval(() => setRemaining(calcRemain()), 1000);
    return () => clearInterval(id);
  });

  if (!remaining) return null;

  return (
    <div className="si-cooldown">
      <span className="si-cooldown-icon">⏱️</span>
      <span>冷却中：{remaining}</span>
    </div>
  );
}

// ══════════════════════════════════════════════
// 辅助函数
// ══════════════════════════════════════════════

function renderFocusMode(focusMode: BeingState["focus_mode"]): string {
  if (focusMode === "morning_plan") return "晨间计划";
  if (focusMode === "autonomy") return "常规自主";
  if (focusMode === "self_improvement") return "自我修复";
  return "休眠";
}

function renderModeLabel(mode: BeingState["mode"]): string {
  return mode === "awake" ? "运行中" : "休眠中";
}

function renderSelfImprovementStatus(
  status: NonNullable<BeingState["self_improvement_job"]>["status"],
): string {
  const map: Record<string, string> = {
    pending: "待开始",
    diagnosing: "诊断中",
    patching: "修补中",
    pending_approval: "待审批",     // Phase 6
    verifying: "验证中",
    applied: "已生效",
    failed: "失败",
    rejected: "已拒绝",            // Phase 6
  };
  return map[status] ?? status;
}

/** 自编程状态 → badge CSS class */
function siStatusClass(status: string): string {
  if (status === "applied") return "completed";
  if (status === "failed") return "abandoned";
  if (status === "rejected") return "abandoned";   // Phase 6
  if (status === "pending_approval") return "active"; // Phase 6
  if (status === "verifying") return "active";
  if (status === "patching") return "active";
  return "paused";
}

function conflictIcon(severity: string): string {
  if (severity === "blocking") return "🚫";
  if (severity === "warning") return "⚠️";
  return "✅";
}

function conflictLabel(severity: string): string {
  if (severity === "blocking") return "阻断冲突";
  if (severity === "warning") return "警告";
  return "安全";
}

function healthColor(score: number): string {
  if (score >= 80) return "var(--success)";
  if (score >= 60) return "var(--info)";
  if (score >= 40) return "var(--warning)";
  return "var(--danger)";
}
