import type { ChatEntry } from "./chatTypes";

type MessageStatusTone = "muted" | "failed";

export type MessageStatus = {
  text: string;
  tone: MessageStatusTone;
};

const REASONING_PHASE_LABELS: Record<string, string> = {
  exploring: "我还在把线索慢慢理顺",
  planning: "我先把接下来的说法整理一下",
  evaluating: "我在对比几个更稳妥的判断",
  finalizing: "我快说完了，正在收一下尾",
  completed: "我已经把这段想清楚了",
};

export function getAssistantStatus(message: ChatEntry, assistantName: string): MessageStatus | null {
  if (message.state === "failed") {
    return {
      text: message.errorMessage?.trim()
        ? `${assistantName}刚才停下来了：${message.errorMessage.trim()}`
        : message.content
          ? `${assistantName}刚才说到这里断开了，你可以让她接着说完。`
          : `${assistantName}这次回复没顺利发出来，可以再叫她继续。`,
      tone: "failed",
    };
  }

  if (message.state === "streaming") {
    if (message.reasoningState?.summary) {
      return {
        text: message.reasoningState.summary,
        tone: "muted",
      };
    }

    if (message.reasoningState?.phase) {
      return {
        text: REASONING_PHASE_LABELS[message.reasoningState.phase] ?? `${assistantName}还在继续想这件事`,
        tone: "muted",
      };
    }

    return {
      text: message.content ? `${assistantName}还在继续说。` : `${assistantName}正在整理这句话。`,
      tone: "muted",
    };
  }

  return null;
}

export function getUserFailedStatus(message: ChatEntry, assistantName: string): MessageStatus {
  return {
    text: message.errorMessage?.trim()
      ? `这句话还没顺利送到${assistantName}那里：${message.errorMessage.trim()}`
      : `这句话还没顺利送到${assistantName}那里。`,
    tone: "failed",
  };
}
