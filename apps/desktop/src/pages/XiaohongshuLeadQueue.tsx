import { useMemo, useState } from "react";

import { Button } from "../components/ui";
import type { XiaohongshuLeadReplyPlan } from "./xiaohongshuLeadReplyHelpers";

type LeadQueueStatus = "pending" | "replied" | "dm" | "wechat" | "closing";

type XiaohongshuLeadQueueProps = {
  plan: XiaohongshuLeadReplyPlan;
};

const STATUS_OPTIONS: Array<{ value: LeadQueueStatus; label: string }> = [
  { value: "pending", label: "待回复" },
  { value: "replied", label: "已回复" },
  { value: "dm", label: "已私信" },
  { value: "wechat", label: "已导微信" },
  { value: "closing", label: "成交前" },
];

export function XiaohongshuLeadQueue({ plan }: XiaohongshuLeadQueueProps) {
  const [statuses, setStatuses] = useState<Record<number, LeadQueueStatus>>({});
  const [notes, setNotes] = useState<Record<number, string>>({});

  const statusSummary = useMemo(() => {
    const counts: Record<LeadQueueStatus, number> = {
      pending: 0,
      replied: 0,
      dm: 0,
      wechat: 0,
      closing: 0,
    };
    plan.suggestions.forEach((_, index) => {
      const status = statuses[index] || "pending";
      counts[status] += 1;
    });
    return counts;
  }, [plan.suggestions, statuses]);

  const outcomeSummary = useMemo(() => {
    const qualifiedItems = plan.suggestions.map((suggestion, index) => {
      const status = statuses[index] || "pending";
      const note = notes[index] || "";
      const qualification = buildQualificationHint({
        commentLine: suggestion.commentLine,
        status,
        note,
      });
      const score = qualificationScore(qualification);
      return {
        suggestion,
        status,
        note,
        qualification,
        score,
      };
    });
    const bestItem = qualifiedItems
      .slice()
      .sort((left, right) => right.score - left.score)[0];
    return {
      hotLeadCount: qualifiedItems.filter((item) => item.score >= 2).length,
      dmCount: qualifiedItems.filter((item) => item.status === "dm").length,
      wechatCount: qualifiedItems.filter((item) => item.status === "wechat").length,
      closingCount: qualifiedItems.filter((item) => item.status === "closing").length,
      bestItem,
      conclusion: buildOutcomeConclusion({
        hotLeadCount: qualifiedItems.filter((item) => item.score >= 2).length,
        dmCount: qualifiedItems.filter((item) => item.status === "dm").length,
        wechatCount: qualifiedItems.filter((item) => item.status === "wechat").length,
        closingCount: qualifiedItems.filter((item) => item.status === "closing").length,
        bestItem,
      }),
    };
  }, [notes, plan.suggestions, statuses]);

  return (
    <div className="xhs-result-card__expanded">
      <strong>待回复名单</strong>
      <div className="xhs-result-card__actions">
        <Button type="button" variant="secondary" onClick={() => void navigator.clipboard.writeText(plan.fullText)}>
          复制承接优先级
        </Button>
      </div>
      <p>{plan.summary}</p>
      <div className="xhs-result-card__expanded">
        <strong>经营结果摘要</strong>
        <p>
          高意向 {outcomeSummary.hotLeadCount} 条，已私信 {outcomeSummary.dmCount} 条，已导微信 {outcomeSummary.wechatCount} 条，
          成交前 {outcomeSummary.closingCount} 条
        </p>
        <p>
          当前最值得跟：{outcomeSummary.bestItem ? outcomeSummary.bestItem.suggestion.commentLine : "暂时还没有明显高价值线索"}
        </p>
        <p>
          当前判断：{outcomeSummary.bestItem ? outcomeSummary.bestItem.qualification : "先继续收评论和私信反馈"}
        </p>
        <p>经营结论：{outcomeSummary.conclusion}</p>
      </div>
      <p>
        当前进度：待回复 {statusSummary.pending}，已回复 {statusSummary.replied}，已私信 {statusSummary.dm}，已导微信{" "}
        {statusSummary.wechat}，成交前 {statusSummary.closing}
      </p>
      {plan.suggestions.map((suggestion, suggestionIndex) => {
        const currentStatus = statuses[suggestionIndex] || "pending";
        const currentNote = notes[suggestionIndex] || "";
        const qualification = buildQualificationHint({
          commentLine: suggestion.commentLine,
          status: currentStatus,
          note: currentNote,
        });
        return (
          <div key={`${suggestion.commentLine}-${suggestionIndex}`} className="xhs-result-card__expanded">
            <strong>{`${suggestionIndex + 1}. ${suggestion.priorityLabel}`}</strong>
            <p>原评论：{suggestion.commentLine}</p>
            <p>建议动作：{suggestion.recommendedAction}</p>
            <p>当前状态：{readableStatus(currentStatus)}</p>
            <p>成交可能性：{qualification}</p>
            <div className="xhs-result-card__actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => void navigator.clipboard.writeText(suggestion.replyDraft)}
              >
                {`复制回复 ${suggestionIndex + 1}`}
              </Button>
              {STATUS_OPTIONS.map((option) => (
                <Button
                  key={`${suggestionIndex}-${option.value}`}
                  type="button"
                  variant={currentStatus === option.value ? "primary" : "secondary"}
                  onClick={() =>
                    setStatuses((current) => ({
                      ...current,
                      [suggestionIndex]: option.value,
                    }))
                  }
                >
                  {option.label}
                </Button>
              ))}
            </div>
            <label>
              <span>跟进备注</span>
              <textarea
                value={currentNote}
                placeholder="例如：预算 3000，本周可聊，想做减脂赛道"
                rows={3}
                onChange={(event) =>
                  setNotes((current) => ({
                    ...current,
                    [suggestionIndex]: event.target.value,
                  }))
                }
              />
            </label>
            <pre>{suggestion.replyDraft}</pre>
          </div>
        );
      })}
      <pre>{plan.fullText}</pre>
    </div>
  );
}

function readableStatus(status: LeadQueueStatus): string {
  return STATUS_OPTIONS.find((option) => option.value === status)?.label || "待回复";
}

function buildQualificationHint({
  commentLine,
  status,
  note,
}: {
  commentLine: string;
  status: LeadQueueStatus;
  note: string;
}): string {
  const combined = `${commentLine} ${note}`.toLowerCase();
  let score = 0;

  if (combined.includes("预算") || combined.includes("报价") || combined.includes("价格")) {
    score += 2;
  }
  if (combined.includes("微信") || combined.includes("vx") || combined.includes("私信")) {
    score += 2;
  }
  if (combined.includes("今天") || combined.includes("明天") || combined.includes("本周") || combined.includes("时间")) {
    score += 1;
  }
  if (combined.includes("方案") || combined.includes("合作") || combined.includes("报名") || combined.includes("想做")) {
    score += 1;
  }
  if (status === "dm") {
    score += 1;
  }
  if (status === "wechat") {
    score += 2;
  }
  if (status === "closing") {
    score += 3;
  }

  if (score >= 5) {
    return "高，建议优先跟到底";
  }
  if (score >= 3) {
    return "中，值得继续追问预算和时间";
  }
  return "低，先轻量承接观察反应";
}

function qualificationScore(value: string): number {
  if (value.startsWith("高")) {
    return 3;
  }
  if (value.startsWith("中")) {
    return 2;
  }
  return 1;
}

function buildOutcomeConclusion({
  hotLeadCount,
  dmCount,
  wechatCount,
  closingCount,
  bestItem,
}: {
  hotLeadCount: number;
  dmCount: number;
  wechatCount: number;
  closingCount: number;
  bestItem:
    | {
        qualification: string;
      }
    | undefined;
}): string {
  if (closingCount > 0) {
    return "这条内容已经出现接近成交的信号，建议优先跟进到结果。";
  }
  if (wechatCount > 0 || dmCount > 0 || bestItem?.qualification.startsWith("高")) {
    return "这条内容已经出现较强承接苗头，值得继续追并放大同类内容。";
  }
  if (hotLeadCount > 0 || bestItem?.qualification.startsWith("中")) {
    return "这条内容更适合先引流和筛选意向，继续追问预算与时间。";
  }
  return "这条内容当前只有轻互动，建议换角度重发或优化钩子。";
}
