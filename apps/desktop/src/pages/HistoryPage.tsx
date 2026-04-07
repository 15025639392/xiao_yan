import { useState } from "react";

import { HistoryPanel } from "../components/HistoryPanel";
import type { SelfProgrammingHistoryEntry } from "../lib/api";

export function HistoryPage({ onSelectRollback }: { onSelectRollback?: (jobId: string) => void }) {
  const [selectedEntry, setSelectedEntry] = useState<SelfProgrammingHistoryEntry | null>(null);

  return (
    <div className="history-page">
      <HistoryPanel visible={true} onSelectEntry={(entry) => setSelectedEntry(entry)} />

      {selectedEntry ? (
        <aside className="history-detail">
          <header className="history-detail__header">
            <h3>详情</h3>
            <button type="button" className="btn btn--sm" onClick={() => setSelectedEntry(null)}>
              关闭
            </button>
          </header>
          <div className="history-detail__body">
            <dl className="history-detail__list">
              <dt>Job ID</dt>
              <dd>{selectedEntry.job_id}</dd>
              <dt>目标区域</dt>
              <dd>{selectedEntry.target_area}</dd>
              <dt>原因</dt>
              <dd>{selectedEntry.reason_statement ?? selectedEntry.reason}</dd>
              {selectedEntry.direction_statement ? (
                <>
                  <dt>方向</dt>
                  <dd>{selectedEntry.direction_statement}</dd>
                </>
              ) : null}
              <dt>结果</dt>
              <dd>{selectedEntry.outcome}</dd>
              <dt>状态</dt>
              <dd>{historyStatusLabel(selectedEntry.status)}</dd>
              <dt>创建时间</dt>
              <dd>{new Date(selectedEntry.created_at).toLocaleString("zh-CN")}</dd>
              {selectedEntry.rejection_reason ? (
                <>
                  <dt>拒绝原因</dt>
                  <dd>{selectedEntry.rejection_reason}</dd>
                </>
              ) : null}
            </dl>

            {selectedEntry.touched_files.length > 0 ? (
              <div className="history-detail__section">
                <h4>触碰文件</h4>
                <ul className="history-detail__files">
                  {selectedEntry.touched_files.map((f: string) => (
                    <li key={f}>
                      <code>{f}</code>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {selectedEntry.health_score != null ? (
              <div className="history-detail__section">
                <h4>健康度</h4>
                <span
                  style={{ fontSize: "1.5rem", fontWeight: 700, color: healthColor(selectedEntry.health_score) }}
                >
                  {selectedEntry.health_score.toFixed(0)}
                </span>
                <span style={{ color: "var(--text-tertiary)", marginLeft: varStr("space-2") }}>分</span>
              </div>
            ) : null}

            {onSelectRollback && selectedEntry.status === "applied" ? (
              <button
                type="button"
                className="btn btn--danger"
                onClick={() => {
                  onSelectRollback(selectedEntry.job_id);
                  setSelectedEntry(null);
                }}
                style={{ marginTop: varStr("space-4"), width: "100%" }}
              >
                ↩️ 回滚此操作
              </button>
            ) : null}
          </div>
        </aside>
      ) : null}
    </div>
  );
}

function varStr(name: string): string {
  return `var(--${name})`;
}

function historyStatusLabel(status: string): string {
  const map: Record<string, string> = {
    drafted: "草案",
    pending_start_approval: "待开工审批",
    queued: "已排队",
    running: "执行中",
    completed: "已完成",
    frozen: "已冻结",
    applied: "已生效",
    failed: "失败",
    verifying: "验证中",
    patching: "修补中",
    diagnosing: "诊断中",
    pending: "待开始",
    pending_approval: "待审批",
    rejected: "已拒绝",
  };
  return map[status] ?? status;
}

function healthColor(score: number): string {
  if (score >= 80) return "var(--success)";
  if (score >= 60) return "var(--info)";
  if (score >= 40) return "var(--warning)";
  return "var(--danger)";
}
