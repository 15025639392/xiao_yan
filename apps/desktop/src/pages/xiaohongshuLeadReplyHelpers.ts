import type { XiaohongshuCreatorPreviewItem, XiaohongshuLeadCaptureResponse } from "../lib/api";

export type XiaohongshuLeadReplySuggestion = {
  priorityLabel: string;
  commentLine: string;
  recommendedAction: string;
  replyDraft: string;
};

export type XiaohongshuLeadReplyPlan = {
  summary: string;
  suggestions: XiaohongshuLeadReplySuggestion[];
  fullText: string;
};

export function buildLeadReplyPlan(
  item: XiaohongshuCreatorPreviewItem,
  leadCaptureResult: XiaohongshuLeadCaptureResponse,
): XiaohongshuLeadReplyPlan {
  const suggestions = leadCaptureResult.matched_comment_lines
    .slice(0, 5)
    .map((line, index) => buildLeadReplySuggestion(item, line, index));
  const summary =
    suggestions.length > 0
      ? `当前页已命中 ${suggestions.length} 条值得优先承接的评论，先从最接近私信、微信和报价的人开始回复。`
      : "当前页暂时没抓到足够明确的高意向评论，先人工看最新评论，再补回复。";
  const fullText = [
    "高意向评论优先回复：",
    summary,
    "",
    ...suggestions.flatMap((suggestion, index) => [
      `${index + 1}. ${suggestion.priorityLabel}`,
      `评论：${suggestion.commentLine}`,
      `动作：${suggestion.recommendedAction}`,
      `建议回复：${suggestion.replyDraft}`,
      "",
    ]),
  ].join("\n").trim();

  return {
    summary,
    suggestions,
    fullText,
  };
}

function buildLeadReplySuggestion(
  item: XiaohongshuCreatorPreviewItem,
  commentLine: string,
  index: number,
): XiaohongshuLeadReplySuggestion {
  const normalized = commentLine.toLowerCase();
  const priorityLabel = resolvePriorityLabel(normalized, index);
  const recommendedAction = resolveRecommendedAction(normalized);
  const replyDraft = buildReplyDraft(item, normalized);
  return {
    priorityLabel,
    commentLine,
    recommendedAction,
    replyDraft,
  };
}

function resolvePriorityLabel(commentLine: string, index: number): string {
  if (commentLine.includes("微信") || commentLine.includes("vx") || commentLine.includes("加v")) {
    return "优先级 P1：马上承接并尽快导到微信";
  }
  if (commentLine.includes("报价") || commentLine.includes("价格") || commentLine.includes("预算")) {
    return "优先级 P1：先确认需求，再推进报价";
  }
  if (commentLine.includes("私信") || commentLine.includes("私聊")) {
    return "优先级 P2：先转私信细聊";
  }
  return index === 0 ? "优先级 P2：优先回复并继续追问" : "优先级 P3：标准跟进回复";
}

function resolveRecommendedAction(commentLine: string): string {
  if (commentLine.includes("微信") || commentLine.includes("vx") || commentLine.includes("加v")) {
    return "先在评论区接住，再马上私信给微信承接话术。";
  }
  if (commentLine.includes("报价") || commentLine.includes("价格") || commentLine.includes("预算")) {
    return "先问清场景、预算和目标，再决定是否继续报价。";
  }
  if (commentLine.includes("私信") || commentLine.includes("私聊")) {
    return "先评论区回应，再引导到私信继续聊。";
  }
  return "先用低压力回复接住，再追问当前阶段和卡点。";
}

function buildReplyDraft(item: XiaohongshuCreatorPreviewItem, normalized: string): string {
  const sourceText = item.platform_result.event.text.trim();
  const topicHint = sourceText.split("\n").find((line) => line.includes("#"))?.trim() || "这条内容";
  if (normalized.includes("微信") || normalized.includes("vx") || normalized.includes("加v")) {
    return "可以，我先在这边接住你。你把你现在做的方向和最卡的点私信我，我先帮你判断一下；如果确认适合深入聊，我们再转微信继续。";
  }
  if (normalized.includes("报价") || normalized.includes("价格") || normalized.includes("预算")) {
    return `可以聊价格，但我建议先别急着报。你先告诉我你现在的阶段、预算区间和想做成什么结果，我再判断“${topicHint}”更适合你用哪种做法。`;
  }
  if (normalized.includes("私信") || normalized.includes("私聊")) {
    return "可以，你直接私信我你现在的情况就行。我先按你的阶段帮你拆一版更具体的执行步骤，再看要不要继续往下聊。";
  }
  if (normalized.includes("怎么") || normalized.includes("如何") || normalized.includes("适合")) {
    return "可以的。你先说下你现在是刚开始，还是已经发过内容但没转化，我再按你的阶段告诉你下一步先做什么。";
  }
  return `收到，这条“${topicHint}”我建议先别一口气做太大。你如果愿意，可以直接告诉我你最想解决的一个问题，我按那个点先帮你细化。`;
}
