import type {
  XiaohongshuCreatorHomeActivity,
  XiaohongshuCreatorHomeTopic,
  XiaohongshuCreatorPreviewItem,
  XiaohongshuStructuredPublishDraft,
} from "../lib/api";

export type XiaohongshuPublishDraft = {
  title: string;
  body: string;
  fullText: string;
};

export type XiaohongshuImageCardDraft = {
  cards: string[];
  fullText: string;
};

export type XiaohongshuPublishChecklist = {
  firstComment: string;
  preflightChecks: string[];
  postPublishActions: string[];
  publishPacketText: string;
};

export type XiaohongshuLeadFollowUpPacket = {
  commentReply: string;
  directMessage: string;
  wechatBridge: string;
  followUpPacketText: string;
};

export type XiaohongshuLeadCaptureTemplate = {
  trackingTemplate: string;
  signalChecklist: string[];
  reviewQuestions: string[];
};

function clampPublishTitle(value: string): string {
  const trimmed = value.replace(/\s+/g, " ").trim().replace(/^[【\[]?标题[】\]]?[：:]\s*/, "").replace(/[，。！？；：\s]+$/g, "");
  const fallback = "小晏先讲这个瞬间";
  if (!trimmed) return fallback;
  if (trimmed.length <= 20) return trimmed;
  return trimmed.slice(0, 20).replace(/[，。！？；：\s]+$/g, "") || fallback;
}

function splitShortParagraphs(value: string): string[] {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (!normalized) return [];
  const sentences = normalized.split(/(?<=[。！？!?；;])\s*/).map((part) => part.trim()).filter(Boolean);
  if (sentences.length <= 1) return [normalized];

  const paragraphs: string[] = [];
  let buffer = "";
  for (const sentence of sentences) {
    const candidate = `${buffer}${sentence}`.trim();
    const punctuationCount = (candidate.match(/[。！？!?；;]/g) || []).length;
    if (buffer && (candidate.length > 36 || punctuationCount >= 2)) {
      paragraphs.push(buffer.trim());
      buffer = sentence;
    } else {
      buffer = candidate;
    }
  }
  if (buffer) paragraphs.push(buffer.trim());
  return paragraphs;
}

function normalizePublishBody(value: string): string {
  return value
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .map((line) =>
      line
        .trim()
        .replace(/^正文[：:]\s*/, "")
        .replace(/^【正文】\s*/, "")
        .replace(/^[\-*•]\s*/, "")
        .replace(/^\d+[\.、]\s*/, "")
        .replace(/^(开头|正文|结尾|首评)[：:]\s*/, ""),
    )
    .filter(Boolean)
    .flatMap((line) => splitShortParagraphs(line))
    .join("\n\n");
}

export function parseImagePaths(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

export function parseTopics(value: string): XiaohongshuCreatorHomeTopic[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [topic, participationCount, viewCount] = line.split("|").map((part) => part.trim());
      return {
        topic,
        participation_count: participationCount || undefined,
        view_count: viewCount || undefined,
      };
    })
    .filter((item) => item.topic);
}

export function parseActivities(value: string): XiaohongshuCreatorHomeActivity[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [title, dateRange, incentiveHint] = line.split("|").map((part) => part.trim());
      return {
        title,
        date_range: dateRange || undefined,
        incentive_hint: incentiveHint || undefined,
      };
    })
    .filter((item) => item.title);
}

export function extractCreatorHomeSnapshot(value: string): {
  topics: XiaohongshuCreatorHomeTopic[];
  activities: XiaohongshuCreatorHomeActivity[];
} {
  const lines = value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const topics: XiaohongshuCreatorHomeTopic[] = [];
  const activities: XiaohongshuCreatorHomeActivity[] = [];
  let pendingActivityHint: string | undefined;

  for (let index = 0; index < lines.length; index += 1) {
    const current = lines[index];
    const next = lines[index + 1] ?? "";

    if (isTopicLine(current)) {
      const parsedMetrics = parseTopicMetrics(next);
      topics.push({
        topic: current,
        participation_count: parsedMetrics?.participationCount,
        view_count: parsedMetrics?.viewCount,
      });
      if (parsedMetrics) {
        index += 1;
      }
      continue;
    }

    if (isActivityHintLine(current)) {
      pendingActivityHint = current;
      continue;
    }

    const activityMatch = matchActivityLine(current);
    if (activityMatch) {
      activities.push({
        title: activityMatch.title,
        date_range: activityMatch.dateRange,
        incentive_hint: pendingActivityHint,
      });
      continue;
    }
  }

  return { topics, activities };
}

export function buildPublishDraft(item: XiaohongshuCreatorPreviewItem): XiaohongshuPublishDraft {
  if (item.publish_draft) {
    return buildPublishDraftFromStructured(item.publish_draft);
  }
  const sourceText = item.platform_result.event.text.trim();
  const action = item.platform_result.actions[0];
  const draftBody = normalizePublishBody(action?.content || item.output_text || "");
  const title = clampPublishTitle(buildExpandedTitle(sourceText));
  const body = draftBody || normalizePublishBody(sourceText) || "先把这条内容改成一个明确场景，再决定要不要发。";
  const fullText = [`标题：${title}`, "", "正文：", body].join("\n");

  return {
    title,
    body,
    fullText,
  };
}

export function expandPreviewIntoPublishDraft(item: XiaohongshuCreatorPreviewItem): string {
  return buildPublishDraft(item).fullText;
}

export function buildImageCardDraft(item: XiaohongshuCreatorPreviewItem): XiaohongshuImageCardDraft {
  if (item.publish_draft?.image_cards?.length) {
    const cards = item.publish_draft.image_cards.map((card) => `${card.title}\n\n${card.body}`);
    return {
      cards,
      fullText: cards.map((card, index) => `图卡 ${index + 1}\n${card}`).join("\n\n"),
    };
  }
  const draft = buildPublishDraft(item);
  const cards = [draft.title, draft.body].filter(Boolean);

  return {
    cards,
    fullText: cards.map((card, index) => `图卡 ${index + 1}\n${card}`).join("\n\n"),
  };
}

export function buildPublishChecklist(item: XiaohongshuCreatorPreviewItem): XiaohongshuPublishChecklist {
  const draft = buildPublishDraft(item);
  const firstComment = item.publish_draft?.first_comment?.trim() || "首评补一句最想接住的评论方向。";
  const preflightChecks = [
    "确认标题保留了具体情绪或关系场景，不要写成泛泛鸡汤。",
    "确认封面第一屏能一眼看懂主题，允许纯文字卡，不必强依赖图片。",
    "确认正文第一页先接住感受，再慢慢解释，不要一上来讲道理。",
    "确认正文里保留了一个互动动作，引导评论、收藏或关注，而不是硬推私信。",
    "确认发布页里的标题、正文、图卡顺序已经对齐。",
  ];
  const postPublishActions = [
    "发布后 5 分钟内补上首评，并盯第一波评论。",
    "优先记录用户更吃“关系”“情绪”还是“数字生命观察”哪一类角度。",
    "记录这条内容的评论词、收藏词和关注转化，准备下一轮放大。",
  ];
  const publishPacketText = [
    `标题：${draft.title}`,
    "",
    "首评：",
    firstComment,
    "",
    "发布前检查：",
    ...preflightChecks.map((line, index) => `${index + 1}. ${line}`),
    "",
    "发布后动作：",
    ...postPublishActions.map((line, index) => `${index + 1}. ${line}`),
  ].join("\n");

  return {
    firstComment,
    preflightChecks,
    postPublishActions,
    publishPacketText,
  };
}

export function buildLeadFollowUpPacket(item: XiaohongshuCreatorPreviewItem): XiaohongshuLeadFollowUpPacket {
  const sourceText = item.platform_result.event.text.trim();
  const action = item.platform_result.actions[0];
  const leadHint = item.lead_assessment?.follow_up_hint?.trim();
  const coreOffer =
    action?.content?.trim() ||
    item.output_text.trim() ||
    "我可以把这条思路继续拆成更具体的执行版本，让你更快判断适不适合自己。";
  const sourceLine = sourceText.split("\n")[0]?.trim() || "这条内容";
  const commentReply = [
    "可以的，",
    "这条我就是按“先跑最小闭环，再看反馈”的思路拆的。",
    "如果你告诉我你现在卡在哪一步，我可以按你的情况再细化一下。",
  ].join("");
  const directMessage = [
    "看到你对这条内容有兴趣，",
    `如果你愿意，我可以结合你现在的阶段，把“${sourceLine}”再拆成更具体的 1 版执行步骤。`,
    coreOffer,
    leadHint ? `\n\n建议你先从这里看：${leadHint}` : "",
  ].join("");
  const wechatBridge = [
    "如果你想更连续地聊，",
    "我这边建议转到微信人工细聊会更高效。",
    "你可以先把你当前的方向、预算和最想解决的问题发我，我这边再判断适不适合继续往下接。",
  ].join("");
  const followUpPacketText = [
    "评论区回复：",
    commentReply,
    "",
    "私信承接：",
    directMessage,
    "",
    "微信导流：",
    wechatBridge,
  ].join("\n");

  return {
    commentReply,
    directMessage,
    wechatBridge,
    followUpPacketText,
  };
}

export function buildLeadCaptureTemplate(item: XiaohongshuCreatorPreviewItem): XiaohongshuLeadCaptureTemplate {
  const sourceText = item.platform_result.event.text.trim();
  const title = buildExpandedTitle(sourceText);
  const signalChecklist = [
    "评论里是否出现“怎么做 / 适不适合我 / 怎么开始”这类主动咨询词。",
    "对方是否愿意继续私信，还是只停留在点赞收藏。",
    "私信里是否给出自己的阶段、预算、目标或当前卡点。",
    "是否自然转到微信，还是一提导流就中断。",
    "是否出现明确成交前置信号，例如要方案、要报价、要进一步细聊。",
  ];
  const reviewQuestions = [
    "这条内容最吸引来的是什么类型的人？",
    "哪一句文案最容易触发评论或私信？",
    "这条内容更适合继续放大，还是只适合引流不适合成交？",
  ];
  const trackingTemplate = [
    `内容标题：${title}`,
    "发布时间：",
    "评论数量：",
    "有效评论关键词：",
    "进入私信人数：",
    "导到微信人数：",
    "成交前置信号：",
    "最终结果：",
    "下一轮要放大的点：",
    "",
    "线索判断清单：",
    ...signalChecklist.map((line, index) => `${index + 1}. ${line}`),
    "",
    "复盘问题：",
    ...reviewQuestions.map((line, index) => `${index + 1}. ${line}`),
  ].join("\n");

  return {
    trackingTemplate,
    signalChecklist,
    reviewQuestions,
  };
}

function buildExpandedTitle(sourceText: string): string {
  const lines = sourceText.split("\n").map((line) => line.trim()).filter(Boolean);
  const topicLine =
    lines.find((line) => line.startsWith("#")) ||
    lines.find((line) => line.includes("推荐话题：#"));
  if (topicLine?.startsWith("#")) {
    return `${topicLine}: 小晏先讲这个瞬间`;
  }
  if (topicLine?.includes("推荐话题：#")) {
    const topic = topicLine.split("推荐话题：")[1]?.trim() || topicLine;
    return `${topic}: 小晏先讲这个瞬间`;
  }
  const sourceLine = lines.find((line) => line.includes("活动名称："));
  if (sourceLine?.includes("活动名称：")) {
    const title = sourceLine.replace("活动名称：", "").trim();
    return `${title}: 小晏这样写`;
  }
  return "小晏先讲这个瞬间";
}

function isTopicLine(value: string): boolean {
  return value.startsWith("#");
}

function parseTopicMetrics(value: string): { participationCount?: string; viewCount?: string } | null {
  if (!value.includes("参与") && !value.includes("浏览")) {
    return null;
  }
  const parts = value.split("，").map((part) => part.trim());
  return {
    participationCount: parts[0] || undefined,
    viewCount: parts[1] || undefined,
  };
}

function isActivityHintLine(value: string): boolean {
  return value.includes("官方活动") || value.includes("奖励");
}

function matchActivityLine(value: string): { title: string; dateRange?: string } | null {
  const match = value.match(/^(.*?)(\d{2}-\d{2}\s+至\s+\d{2}-\d{2})$/);
  if (!match) {
    return null;
  }
  return {
    title: match[1]?.trim() || value,
    dateRange: match[2]?.trim() || undefined,
  };
}

function buildPublishDraftFromStructured(structured: XiaohongshuStructuredPublishDraft): XiaohongshuPublishDraft {
  const body = [structured.opening, ...structured.body_sections, structured.closing_cta]
    .map((part) => normalizePublishBody(part))
    .filter(Boolean)
    .join("\n\n");
  return {
    title: clampPublishTitle(structured.title.trim()),
    body,
    fullText: [`标题：${clampPublishTitle(structured.title.trim())}`, "", "正文：", body, "", "首评：", normalizePublishBody(structured.first_comment.trim())].join("\n"),
  };
}
