import {
  hasKnowledgeReferences,
  hasRecoverableAssistantReply,
  hasRelatedMemories,
  hasRetryableUserSend,
  isAssistantChatEntry,
  type ChatEntry,
} from "./chatTypes";

type MessageStatusTone = "muted" | "failed";
export type ChatMessageBodyMode = "markdown" | "streaming-placeholder" | "plain-text" | "none";

export type MessageStatus = {
  text: string;
  tone: MessageStatusTone;
};

export type ChatMessageDisplayState = {
  bodyMode: ChatMessageBodyMode;
  status: MessageStatus | null;
  showKnowledgeContext: boolean;
  showMemoryContext: boolean;
  showResumeAction: boolean;
  showRetryAction: boolean;
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

  if (message.state === "streaming" && message.content.trim()) {
    return {
      text: `${assistantName}还在继续说`,
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

export function getChatMessageDisplayState(
  message: ChatEntry,
  assistantName: string,
): ChatMessageDisplayState {
  const isAssistant = isAssistantChatEntry(message);
  const hasAssistantContent = isAssistant && Boolean(message.content);
  const assistantStatus = isAssistant ? getAssistantStatus(message, assistantName) : null;

  if (isAssistant) {
    return {
      bodyMode: hasAssistantContent
        ? "markdown"
        : message.state === "streaming"
          ? "streaming-placeholder"
          : "none",
      status: assistantStatus,
      showKnowledgeContext: hasKnowledgeReferences(message),
      showMemoryContext: hasRelatedMemories(message),
      showResumeAction: hasRecoverableAssistantReply(message),
      showRetryAction: false,
    };
  }

  return {
    bodyMode: "plain-text",
    status: message.state === "failed" ? getUserFailedStatus(message, assistantName) : null,
    showKnowledgeContext: false,
    showMemoryContext: false,
    showResumeAction: false,
    showRetryAction: hasRetryableUserSend(message),
  };
}
