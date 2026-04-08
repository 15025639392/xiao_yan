import type {
  DeferredGoalAdmissionCandidate,
  GoalAdmissionCandidateSnapshot,
  RecentGoalAdmissionDecision,
} from "../../lib/api";
import { SurfaceCard } from "../ui";

type GoalsAdmissionCandidatesProps = {
  snapshot: GoalAdmissionCandidateSnapshot | null;
};

function describeDeferredReason(reason: string): string {
  if (reason === "user_score" || reason === "world_score" || reason === "chain_score") {
    return "因为分数不足进入延后观察";
  }
  if (reason === "wip_full") {
    return "因为当前并行目标已满，先进入延后观察";
  }
  if (reason === "duplicate_candidate") {
    return "因为刚出现过相似候选，先进入延后观察";
  }
  return `因为 ${reason} 进入延后观察`;
}

function describeRecentDecision(item: RecentGoalAdmissionDecision): string {
  if (item.reason.startsWith("relationship_boundary:")) {
    return "因为关系边界冲突被拦下";
  }
  if (item.reason.startsWith("value_boundary:")) {
    return "因为价值边界冲突被拦下";
  }
  if (item.decision === "defer") {
    return describeDeferredReason(item.reason);
  }
  return `因为 ${item.reason} 被拦下`;
}

function describeReasonDetail(reason: string): string | null {
  if (reason.startsWith("relationship_boundary:")) {
    return `关系边界：${reason.replace("relationship_boundary:", "")}`;
  }
  if (reason.startsWith("value_boundary:")) {
    return `价值边界：${reason.replace("value_boundary:", "")}`;
  }
  return null;
}

function formatRetryAt(nextRetryAt: string): string {
  const matched = nextRetryAt.match(/T(\d{2}:\d{2})/);
  return matched ? matched[1] : nextRetryAt;
}

function sourceLabel(sourceType: DeferredGoalAdmissionCandidate["candidate"]["source_type"]): string {
  if (sourceType === "world_event") {
    return "世界事件";
  }
  if (sourceType === "chain_next") {
    return "链式续推";
  }
  return "用户话题";
}

function renderDeferredItem(item: DeferredGoalAdmissionCandidate) {
  return (
    <SurfaceCard key={`${item.candidate.fingerprint ?? item.candidate.title}-deferred`}>
      <div className="goals-candidate-pool__item-head">
        <span className="goals-candidate-pool__item-title">{item.candidate.title}</span>
        <span className="goals-candidate-pool__item-chip">{sourceLabel(item.candidate.source_type)}</span>
      </div>
      <div className="goals-candidate-pool__item-text">{describeDeferredReason(item.last_reason)}</div>
      <div className="goals-candidate-pool__item-meta">{`下次重试 ${formatRetryAt(item.next_retry_at)}`}</div>
    </SurfaceCard>
  );
}

function renderRecentItem(item: RecentGoalAdmissionDecision) {
  return (
    <SurfaceCard key={`${item.candidate.fingerprint ?? item.candidate.title}-${item.created_at}`}>
      <div className="goals-candidate-pool__item-head">
        <span className="goals-candidate-pool__item-title">{item.candidate.title}</span>
        <span className={`goals-candidate-pool__item-chip goals-candidate-pool__item-chip--${item.decision}`}>
          {item.decision === "drop" ? "已拦下" : "已延后"}
        </span>
      </div>
      <div className="goals-candidate-pool__item-text">{describeRecentDecision(item)}</div>
      {describeReasonDetail(item.reason) ? (
        <div className="goals-candidate-pool__item-meta">{describeReasonDetail(item.reason)}</div>
      ) : null}
    </SurfaceCard>
  );
}

export function GoalsAdmissionCandidates({ snapshot }: GoalsAdmissionCandidatesProps) {
  const admitted = snapshot?.admitted ?? [];
  if (!snapshot || (snapshot.deferred.length === 0 && snapshot.recent.length === 0 && admitted.length === 0)) {
    return null;
  }

  return (
    <section className="goals-candidate-pool" aria-label="候选目标池">
      <div className="goals-candidate-pool__header">
        <span className="goals-candidate-pool__title">候选目标池</span>
        <span className="goals-candidate-pool__hint">让准入不再是黑箱：哪些在观察，哪些刚被拦下，都能看见。</span>
      </div>

      <div className="goals-candidate-pool__columns">
        <div className="goals-candidate-pool__group">
          <div className="goals-candidate-pool__group-title">延后观察</div>
          <div className="goals-candidate-pool__items">
            {snapshot.deferred.length > 0 ? (
              snapshot.deferred.map(renderDeferredItem)
            ) : (
              <div className="goals-candidate-pool__empty">当前没有延后观察中的候选。</div>
            )}
          </div>
        </div>

        <div className="goals-candidate-pool__group">
          <div className="goals-candidate-pool__group-title">最近拦截</div>
          <div className="goals-candidate-pool__items">
            {snapshot.recent.length > 0 ? (
              snapshot.recent.map(renderRecentItem)
            ) : (
              <div className="goals-candidate-pool__empty">最近没有被拦下的候选。</div>
            )}
          </div>
        </div>

        <div className="goals-candidate-pool__group">
          <div className="goals-candidate-pool__group-title">最近转正</div>
          <div className="goals-candidate-pool__items">
            {admitted.length > 0 ? (
              admitted.map((item) => (
                <SurfaceCard key={`${item.candidate.fingerprint ?? item.candidate.title}-${item.created_at}-admit`}>
                  <div className="goals-candidate-pool__item-head">
                    <span className="goals-candidate-pool__item-title">{item.candidate.title}</span>
                    <span className="goals-candidate-pool__item-chip goals-candidate-pool__item-chip--admit">
                      已转正
                    </span>
                  </div>
                  <div className="goals-candidate-pool__item-text">
                    {item.candidate.retry_count > 0
                      ? `延后 ${item.candidate.retry_count} 次后转正`
                      : "已通过准入进入目标看板"}
                  </div>
                </SurfaceCard>
              ))
            ) : (
              <div className="goals-candidate-pool__empty">最近没有转正候选。</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
