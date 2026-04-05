import { useState } from "react";
import type { SelfProgrammingJob, SelfProgrammingEdit } from "../lib/api";
import {
  approveSelfProgrammingJob,
  rejectSelfProgrammingJob,
} from "../lib/api";

type ApprovalPanelProps = {
  /** 当前需要审批的 Job */
  job: NonNullable<SelfProgrammingJob>;
  /** 审批完成后的回调（批准或拒绝都会触发） */
  onDecision: (jobId: string, approved: boolean) => void;
};

export function ApprovalPanel({ job, onDecision }: ApprovalPanelProps) {
  const [decisioning, setDecisioning] = useState(false);
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [result, setResult] = useState<"approved" | "rejected" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showEdits, setShowEdits] = useState(false);

  const edits = job.edits ?? [];

  async function handleApprove() {
    if (decisioning) return;
    setDecisioning(true);
    setError(null);
    try {
      await approveSelfProgrammingJob(job.id);
      setResult("approved");
      onDecision(job.id, true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "审批失败");
    } finally {
      setDecisioning(false);
    }
  }

  async function handleReject() {
    if (!rejectReason.trim()) {
      setError("请填写拒绝原因");
      return;
    }
    if (decisioning) return;
    setDecisioning(true);
    setError(null);
    try {
      await rejectSelfProgrammingJob(job.id, rejectReason.trim());
      setResult("rejected");
      onDecision(job.id, false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setDecisioning(false);
    }
  }

  // 已出结果 → 展示最终状态
  if (result) {
    return (
      <section className={`approval-panel approval-panel--${result}`}>
        <div className="approval-panel__header">
          <span className="approval-panel__icon">
            {result === "approved" ? "✅" : "🚫"}
          </span>
          <h3 className="approval-panel__title">
            {result === "approved" ? "已批准" : "已拒绝"}
          </h3>
        </div>
        <div className="approval-panel__body">
          <p>
            {result === "approved"
              ? `自我编程方案「${job.target_area}」已被批准，正在继续执行验证流程...`
              : `自我编程方案「${job.target_area}」已被拒绝。${job.approval_reason ?? rejectReason}`
            }
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="approval-panel">
      {/* 头部 */}
      <div className="approval-panel__header">
        <span className="approval-panel__icon">🔔</span>
        <div>
          <h3 className="approval-panel__title">等待审批</h3>
          <p className="approval-panel__subtitle">
            数字人已完成补丁编写，等待你确认是否应用
          </p>
        </div>
        <span className="status-badge status-badge--active">待审批</span>
      </div>

      {/* 审批信息摘要 */}
      <div className="approval-panel__body">
        {/* 目标区域 + 原因 */}
        <div className="approval-summary">
          <div className="approval-summary__row">
            <span className="approval-summary__label">目标区域</span>
            <span className="approval-summary__value">{job.target_area}</span>
          </div>
          <div className="approval-summary__row">
            <span className="approval-summary__label">原因</span>
            <span className="approval-summary__value">{job.reason}</span>
          </div>
          <div className="approval-summary__row">
            <span className="approval-summary__label">方案</span>
            <span className="approval-summary__value">{job.spec}</span>
          </div>
          {job.patch_summary ? (
            <div className="approval-summary__row">
              <span className="approval-summary__label">补丁摘要</span>
              <code className="approval-summary__code">{job.patch_summary}</code>
            </div>
          ) : null}
          {job.approval_edits_summary ? (
            <div className="approval-summary__row">
              <span className="approval-summary__label">编辑内容</span>
              <code className="approval-summary__code">{job.approval_edits_summary}</code>
            </div>
          ) : null}
        </div>

        {/* 触碰文件列表 */}
        {job.touched_files && job.touched_files.length > 0 ? (
          <div className="approval-files">
            <h4 className="approval-files__title">
              将修改 {job.touched_files.length} 个文件：
            </h4>
            <ul className="approval-files__list">
              {job.touched_files.map((fp) => (
                <li key={fp} className="approval-files__item">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-8V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                  </svg>
                  <code>{fp}</code>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {/* Diff 详情（可折叠） */}
        {edits.length > 0 ? (
          <div className="approval-edits">
            <button
              type="button"
              className="approval-edits__toggle"
              onClick={() => setShowEdits(!showEdits)}
            >
              <svg
                width="14" height="14" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" strokeWidth="2"
                style={{ transform: showEdits ? "rotate(180deg)" : "none", transition: "transform 200ms ease" }}
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
              <span>查看代码变更 ({edits.length})</span>
            </button>
            {showEdits ? (
              <div className="approval-edits__list">
                {edits.map((edit, idx) => (
                  <ApprovalDiffItem key={`${edit.file_path}-${idx}`} edit={edit} />
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {/* 错误提示 */}
        {error ? (
          <div className="approval-error">{error}</div>
        ) : null}

        {/* 操作按钮区 */}
        <div className="approval-actions">
          {!showRejectForm ? (
            <>
              {/* 主操作：批准 / 拒绝 */}
              <button
                type="button"
                className="btn btn--primary btn--lg"
                disabled={decisioning}
                onClick={handleApprove}
                style={{ flex: 2 }}
              >
                {decisioning ? "⏳ 处理中..." : "✅ 批准应用"}
              </button>
              <button
                type="button"
                className="btn btn--sm"
                disabled={decisioning}
                onClick={() => setShowRejectForm(true)}
                style={{ flex: 1 }}
              >
                🚫 拒绝
              </button>
            </>
          ) : (
            /* 拒绝表单 */
            <div className="approval-reject-form">
              <label className="approval-reject-form__label" htmlFor="reject-reason">
                请填写拒绝原因（帮助数字人学习）：
              </label>
              <textarea
                id="reject-reason"
                className="approval-reject-form__textarea"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="例如：这个修改范围太大了，我想先看看具体改动..."
                rows={3}
                autoFocus
              />
              <div className="approval-reject-form__actions">
                <button
                  type="button"
                  className="btn btn--sm"
                  onClick={() => { setShowRejectForm(false); setRejectReason(""); }}
                  disabled={decisioning}
                >
                  返回
                </button>
                <button
                  type="button"
                  className="btn btn--danger btn--sm"
                  onClick={handleReject}
                  disabled={decisioning || !rejectReason.trim()}
                >
                  确认拒绝
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

// ══════════════════════════════════════════════
// 子组件：审批用 Diff 展示（精简版）
// ══════════════════════════════════════════════

function ApprovalDiffItem({ edit }: { edit: SelfProgrammingEdit }) {
  const [expanded, setExpanded] = useState(false);

  const kindLabel = edit.kind.toUpperCase();
  const kindClass =
    edit.kind === "create"
      ? "approval-diff-kind--create"
      : edit.kind === "insert"
        ? "approval-diff-kind--insert"
        : "approval-diff-kind--replace";

  return (
    <div className="approval-diff-item">
      <div
        className="approval-diff-header"
        onClick={() => setExpanded(!expanded)}
      >
        <span className={`approval-diff-kind ${kindClass}`}>{kindLabel}</span>
        <code className="approval-diff-path">{edit.file_path}</code>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          style={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform 200ms" }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
      {expanded ? (
        <div className="approval-diff-content">
          {edit.kind === "create" ? (
            <pre><code>{(edit.file_content ?? "").slice(0, 1500)}</code></pre>
          ) : edit.kind === "insert" ? (
            <div>
              <pre className="approval-diff-ctx"><code>... {edit.insert_after ?? "..."} ...</code></pre>
              <pre className="approval-diff-new"><code>+ {(edit.replace_text ?? "").slice(0, 800)}</code></pre>
            </div>
          ) : (
            <div>
              <pre className="approval-diff-old"><code>- {(edit.search_text ?? "").slice(0, 800)}</code></pre>
              <pre className="approval-diff-new"><code>+ {(edit.replace_text ?? "").slice(0, 800)}</code></pre>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
