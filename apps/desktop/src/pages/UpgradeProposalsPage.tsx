import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, CircleSlash, ClipboardList, RefreshCw, Wrench } from "lucide-react";

import { Button } from "../components/ui";
import {
  approveUpgradeProposal,
  fetchUpgradeProposals,
  markUpgradeProposalImplemented,
  rejectUpgradeProposal,
  type UpgradeProposal,
  type UpgradeProposalStatus,
} from "../lib/apiUpgradeProposals";

const STATUS_LABELS: Record<UpgradeProposalStatus, string> = {
  draft: "草稿",
  submitted: "待审批",
  approved: "已通过",
  rejected: "已驳回",
  implemented: "已实施",
  abandoned: "已放弃",
};

const CATEGORY_LABELS: Record<UpgradeProposal["category"], string> = {
  workflow_fix: "流程",
  habit_adjustment: "习惯",
  new_capability: "新能力",
  boundary_tuning: "边界",
};

export function UpgradeProposalsPage() {
  const [proposals, setProposals] = useState<UpgradeProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const pendingCount = useMemo(
    () => proposals.filter((proposal) => proposal.status === "submitted").length,
    [proposals],
  );

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const result = await fetchUpgradeProposals({ limit: 80 });
      setProposals(result.proposals);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载升级计划失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function runAction(proposalId: string, action: () => Promise<{ ok: boolean; message?: string | null }>) {
    setBusyId(proposalId);
    setError("");
    try {
      const result = await action();
      if (!result.ok) {
        throw new Error(result.message || "计划状态不允许当前操作");
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="upgrade-page">
      <header className="upgrade-header">
        <div>
          <h2 className="upgrade-title">升级计划</h2>
          <p className="upgrade-subtitle">{pendingCount > 0 ? `${pendingCount} 条等待你审阅` : "暂无待审批计划"}</p>
        </div>
        <Button type="button" variant="secondary" size="sm" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={15} />
          刷新
        </Button>
      </header>

      {error ? <div className="upgrade-error">{error}</div> : null}

      <section className="upgrade-list" aria-live="polite">
        {loading ? <p className="upgrade-muted">正在读取计划...</p> : null}
        {!loading && proposals.length === 0 ? (
          <div className="upgrade-empty">
            <ClipboardList size={28} />
            <span>还没有升级计划。</span>
          </div>
        ) : null}
        {proposals.map((proposal) => (
          <UpgradeProposalCard
            key={proposal.proposal_id}
            proposal={proposal}
            busy={busyId === proposal.proposal_id}
            onApprove={() => void runAction(proposal.proposal_id, () => approveUpgradeProposal(proposal.proposal_id))}
            onReject={() => {
              const reason = window.prompt("驳回原因", "先暂缓，等边界更清楚。");
              if (!reason?.trim()) return;
              void runAction(proposal.proposal_id, () => rejectUpgradeProposal(proposal.proposal_id, reason.trim()));
            }}
            onImplement={() =>
              void runAction(proposal.proposal_id, () => markUpgradeProposalImplemented(proposal.proposal_id))
            }
          />
        ))}
      </section>
    </div>
  );
}

function UpgradeProposalCard({
  proposal,
  busy,
  onApprove,
  onReject,
  onImplement,
}: {
  proposal: UpgradeProposal;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
  onImplement: () => void;
}) {
  const canReview = proposal.status === "submitted";
  const canImplement = proposal.status === "approved";

  return (
    <article className="upgrade-card">
      <div className="upgrade-card__head">
        <div>
          <span className="upgrade-card__id">{proposal.proposal_id}</span>
          <h3>{proposal.her_voice}</h3>
        </div>
        <span className={`upgrade-status upgrade-status--${proposal.status}`}>{STATUS_LABELS[proposal.status]}</span>
      </div>

      <dl className="upgrade-meta">
        <div>
          <dt>类型</dt>
          <dd>{CATEGORY_LABELS[proposal.category]}</dd>
        </div>
        <div>
          <dt>领域</dt>
          <dd>{proposal.target_domain}</dd>
        </div>
        <div>
          <dt>优先级</dt>
          <dd>{proposal.suggested_priority}</dd>
        </div>
      </dl>

      <section className="upgrade-detail">
        <strong>动机</strong>
        <p>{proposal.motivation}</p>
      </section>

      {proposal.pain_points.length > 0 ? (
        <section className="upgrade-detail">
          <strong>痛点</strong>
          <ul>
            {proposal.pain_points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {proposal.reject_reason ? (
        <section className="upgrade-detail">
          <strong>驳回原因</strong>
          <p>{proposal.reject_reason}</p>
        </section>
      ) : null}

      {proposal.observation_notes ? (
        <section className="upgrade-detail">
          <strong>观察记录</strong>
          <p>{proposal.observation_notes}</p>
        </section>
      ) : null}

      <div className="upgrade-actions">
        {canReview ? (
          <>
            <Button type="button" size="sm" onClick={onApprove} disabled={busy}>
              <Check size={15} />
              通过
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={onReject} disabled={busy}>
              <CircleSlash size={15} />
              驳回
            </Button>
          </>
        ) : null}
        {canImplement ? (
          <Button type="button" size="sm" onClick={onImplement} disabled={busy}>
            <Wrench size={15} />
            标记实施
          </Button>
        ) : null}
      </div>
    </article>
  );
}
