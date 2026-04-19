import { useCallback, useEffect, useMemo, useState } from "react";

import {
  approveCapabilityRequest,
  fetchCapabilityApprovalHistory,
  fetchCapabilityContract,
  fetchCapabilityJobs,
  fetchCapabilityPendingApprovals,
  fetchCapabilityQueueStatus,
  rejectCapabilityRequest,
} from "../lib/capabilities/api";
import type {
  CapabilityApprovalHistoryItem,
  CapabilityApprovalPendingItem,
  CapabilityDescriptor,
  CapabilityJobAuditItem,
  CapabilityQueueStatusResponse,
} from "../lib/capabilities/types";
import { Button, Panel, StatusBadge } from "../components/ui";

type CapabilityHubSnapshot = {
  descriptors: CapabilityDescriptor[];
  queueStatus: CapabilityQueueStatusResponse | null;
  jobs: CapabilityJobAuditItem[];
  pendingApprovals: CapabilityApprovalPendingItem[];
  approvalHistory: CapabilityApprovalHistoryItem[];
};

const EMPTY_SNAPSHOT: CapabilityHubSnapshot = {
  descriptors: [],
  queueStatus: null,
  jobs: [],
  pendingApprovals: [],
  approvalHistory: [],
};

export function CapabilitiesPage() {
  const [snapshot, setSnapshot] = useState<CapabilityHubSnapshot>(EMPTY_SNAPSHOT);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [decisionLoadingId, setDecisionLoadingId] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);

  const load = useCallback(async (isRefresh = false) => {
    setError(null);
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const [contract, queueStatus, jobs, pendingApprovals, approvalHistory] = await Promise.all([
        fetchCapabilityContract(),
        fetchCapabilityQueueStatus(),
        fetchCapabilityJobs({ limit: 60 }),
        fetchCapabilityPendingApprovals(30),
        fetchCapabilityApprovalHistory(30),
      ]);

      setSnapshot({
        descriptors: contract.descriptors ?? [],
        queueStatus,
        jobs: jobs.items ?? [],
        pendingApprovals: pendingApprovals.items ?? [],
        approvalHistory: approvalHistory.items ?? [],
      });
      setLastUpdatedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载外部能力详情失败");
    } finally {
      if (isRefresh) {
        setRefreshing(false);
      } else {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void load(false);
  }, [load]);

  const learningJobs = useMemo(
    () =>
      snapshot.jobs.filter(
        (item) => item.status !== "completed" || item.approval_status === "pending",
      ),
    [snapshot.jobs],
  );

  const queue = snapshot.queueStatus;

  return (
    <div className="capability-hub-page">
      <header className="capability-hub-header">
        <div>
          <h2 className="capability-hub-title">外部能力详情</h2>
          <p className="capability-hub-subtitle">集中查看能力清单、审批状态与最近运行记录。</p>
        </div>
        <div className="capability-hub-actions">
          {lastUpdatedAt ? (
            <span className="capability-hub-updated-at">更新于 {formatDateTime(lastUpdatedAt.toISOString())}</span>
          ) : null}
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => void load(true)}
            disabled={loading || refreshing}
          >
            {refreshing ? "刷新中..." : "刷新"}
          </Button>
        </div>
      </header>

      {error ? <div className="tool-error">外部能力详情加载失败：{error}</div> : null}
      {decisionError ? <div className="tool-error">确认操作失败：{decisionError}</div> : null}

      <section className="capability-hub-metrics" aria-label="外部能力运行概览">
        <MetricCard label="排队中" value={queue?.pending ?? 0} />
        <MetricCard label="待确认" value={queue?.pending_approval ?? 0} />
        <MetricCard label="执行中" value={queue?.in_progress ?? 0} />
        <MetricCard label="已完成" value={queue?.completed ?? 0} />
        <MetricCard label="异常中断" value={queue?.dead_letter ?? 0} tone="danger" />
      </section>

      <section className="capability-hub-grid">
        <Panel
          className="capability-hub-panel"
          icon="🧩"
          title="能力清单"
          subtitle="这里列出当前接入的外部能力与默认边界"
          actions={<span className="capability-hub-count">{snapshot.descriptors.length} 项</span>}
        >
          {loading && snapshot.descriptors.length === 0 ? (
            <div className="capability-hub-empty">加载中...</div>
          ) : snapshot.descriptors.length === 0 ? (
            <div className="capability-hub-empty">暂无能力描述</div>
          ) : (
            <ul className="capability-hub-list">
              {snapshot.descriptors.map((descriptor) => (
                <li key={descriptor.name} className="capability-hub-item">
                  <div className="capability-hub-item__head">
                    <strong>{presentCapabilityName(descriptor.name)}</strong>
                    <div className="capability-hub-item__badges">
                      <StatusBadge tone={riskTone(descriptor.default_risk_level)}>
                        {riskLabel(descriptor.default_risk_level)}
                      </StatusBadge>
                      <StatusBadge tone={descriptor.default_requires_approval ? "cap-pending" : "completed"}>
                        {descriptor.default_requires_approval ? "需确认" : "免确认"}
                      </StatusBadge>
                    </div>
                  </div>
                  <p className="capability-hub-item__desc">{descriptor.description}</p>
                  <p className="capability-hub-item__bind">
                    接入方式: <span>{descriptor.current_binding}</span>
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          className="capability-hub-panel"
          icon="🧠"
          title="正在学习的能力"
          subtitle="这里只保留还没走完的能力推进"
          actions={<span className="capability-hub-count">{learningJobs.length} 条</span>}
        >
          {loading && learningJobs.length === 0 ? (
            <div className="capability-hub-empty">加载中...</div>
          ) : learningJobs.length === 0 ? (
            <div className="capability-hub-empty">当前没有学习中的能力任务</div>
          ) : (
            <ul className="capability-hub-list capability-hub-list--dense">
              {learningJobs.map((job) => (
                <li key={job.request_id} className="capability-hub-item">
                  <div className="capability-hub-item__head">
                    <strong>{presentCapabilityName(job.capability)}</strong>
                    <StatusBadge tone={jobTone(job.status)}>{jobStatusLabel(job.status)}</StatusBadge>
                  </div>
                  <div className="capability-hub-item__meta">
                    <span>{renderAttemptLabel(job.attempt, job.max_attempts)}</span>
                    <StatusBadge tone={approvalTone(job.approval_status)}>
                      {approvalStatusLabel(job.approval_status)}
                    </StatusBadge>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          className="capability-hub-panel"
          icon="🚦"
          title="等待确认"
          subtitle="这些能力请求还需要你点头"
          actions={<span className="capability-hub-count">{snapshot.pendingApprovals.length} 条</span>}
        >
          {loading && snapshot.pendingApprovals.length === 0 ? (
            <div className="capability-hub-empty">加载中...</div>
          ) : snapshot.pendingApprovals.length === 0 ? (
            <div className="capability-hub-empty">当前没有等待确认的请求</div>
          ) : (
            <ul className="capability-hub-list capability-hub-list--dense">
              {snapshot.pendingApprovals.map((item) => (
                <li key={item.request.request_id} className="capability-hub-item">
                  <div className="capability-hub-item__head">
                    <strong>{presentCapabilityName(item.request.capability)}</strong>
                    <StatusBadge tone="cap-pending">待确认</StatusBadge>
                  </div>
                  <div className="capability-hub-item__meta">
                    <span>{formatQueuedAtLabel(item.queued_at)}</span>
                  </div>
                  {item.request.context?.reason ? (
                    <p className="capability-hub-item__desc">{item.request.context.reason}</p>
                  ) : null}
                  <div className="capability-hub-item__actions">
                    <Button
                      type="button"
                      variant="default"
                      size="sm"
                      disabled={decisionLoadingId === item.request.request_id}
                      onClick={() => void handleApprove(item.request.request_id)}
                    >
                      {decisionLoadingId === item.request.request_id ? "处理中..." : "允许这次"}
                    </Button>
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      disabled={decisionLoadingId === item.request.request_id}
                      onClick={() => void handleReject(item.request.request_id)}
                    >
                      {decisionLoadingId === item.request.request_id ? "处理中..." : "拒绝"}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          className="capability-hub-panel"
          icon="📜"
          title="确认记录"
          subtitle="最近的确认决定与原因"
          actions={<span className="capability-hub-count">{snapshot.approvalHistory.length} 条</span>}
        >
          {loading && snapshot.approvalHistory.length === 0 ? (
            <div className="capability-hub-empty">加载中...</div>
          ) : snapshot.approvalHistory.length === 0 ? (
            <div className="capability-hub-empty">暂无确认记录</div>
          ) : (
            <ul className="capability-hub-list capability-hub-list--dense">
              {snapshot.approvalHistory.map((item) => (
                <li key={`${item.request_id}-${item.decided_at}`} className="capability-hub-item">
                  <div className="capability-hub-item__head">
                    <strong>{presentCapabilityName(item.capability)}</strong>
                    <StatusBadge tone={item.action === "approved" ? "cap-approved" : "cap-rejected"}>
                      {item.action === "approved" ? "已确认" : "已拒绝"}
                    </StatusBadge>
                  </div>
                  <div className="capability-hub-item__meta">
                    <span>确认人: {item.approver}</span>
                    <span>{formatDateTime(item.decided_at)}</span>
                  </div>
                  {item.reason ? <p className="capability-hub-item__desc">{item.reason}</p> : null}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </section>
    </div>
  );

  async function handleApprove(requestId: string): Promise<void> {
    setDecisionError(null);
    setDecisionLoadingId(requestId);
    try {
      await approveCapabilityRequest(requestId, "desktop-user");
      await load(true);
    } catch (err) {
      setDecisionError(err instanceof Error ? err.message : "批准失败");
    } finally {
      setDecisionLoadingId(null);
    }
  }

  async function handleReject(requestId: string): Promise<void> {
    const reasonRaw = window.prompt("请输入拒绝原因（将记录在确认记录中）：", "");
    if (reasonRaw === null) {
      return;
    }
    const reason = reasonRaw.trim();
    if (!reason) {
      setDecisionError("拒绝原因不能为空");
      return;
    }

    setDecisionError(null);
    setDecisionLoadingId(requestId);
    try {
      await rejectCapabilityRequest(requestId, reason, "desktop-user");
      await load(true);
    } catch (err) {
      setDecisionError(err instanceof Error ? err.message : "拒绝失败");
    } finally {
      setDecisionLoadingId(null);
    }
  }
}

function MetricCard({ label, value, tone = "default" }: { label: string; value: number; tone?: "default" | "danger" }) {
  return (
    <article className={`capability-metric capability-metric--${tone}`}>
      <span className="capability-metric__label">{label}</span>
      <strong className="capability-metric__value">{value}</strong>
    </article>
  );
}

function riskLabel(risk: "safe" | "restricted" | "dangerous"): string {
  if (risk === "safe") return "安全";
  if (risk === "restricted") return "受限";
  return "高危";
}

function presentCapabilityName(name: CapabilityDescriptor["name"]): string {
  if (name === "fs.read") return "读取文件";
  if (name === "fs.write") return "写入文件";
  if (name === "fs.list") return "查看文件列表";
  if (name === "fs.search") return "搜索文件内容";
  if (name === "shell.run") return "执行命令";
  return name;
}

function riskTone(risk: "safe" | "restricted" | "dangerous"): string {
  if (risk === "safe") return "cap-safe";
  if (risk === "restricted") return "cap-restricted";
  return "cap-dangerous";
}

function jobTone(status: "pending" | "in_progress" | "completed"): string {
  if (status === "completed") return "completed";
  if (status === "in_progress") return "active";
  return "paused";
}

function jobStatusLabel(status: "pending" | "in_progress" | "completed"): string {
  if (status === "completed") return "已完成";
  if (status === "in_progress") return "执行中";
  return "排队中";
}

function approvalTone(status: "not_required" | "pending" | "approved" | "rejected"): string {
  if (status === "approved") return "cap-approved";
  if (status === "rejected") return "cap-rejected";
  if (status === "pending") return "cap-pending";
  return "completed";
}

function approvalStatusLabel(status: "not_required" | "pending" | "approved" | "rejected"): string {
  if (status === "approved") return "已确认";
  if (status === "rejected") return "已拒绝";
  if (status === "pending") return "待确认";
  return "免确认";
}

function renderAttemptLabel(attempt: number, maxAttempts: number): string {
  if (maxAttempts <= 1) {
    return "当前推进中";
  }
  return `第 ${attempt} 次尝试，共 ${maxAttempts} 次机会`;
}

function formatQueuedAtLabel(iso: string): string {
  return `进入等待于 ${formatDateTime(iso)}`;
}

function formatDateTime(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return iso;
  }
  return parsed.toLocaleString("zh-CN");
}
