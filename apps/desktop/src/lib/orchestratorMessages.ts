import type { OrchestratorMessage } from "./api";

export function mergeOrchestratorMessages(
  current: OrchestratorMessage[],
  incoming: OrchestratorMessage[] | undefined | null,
): OrchestratorMessage[] {
  if (!Array.isArray(incoming) || incoming.length === 0) {
    return [...current];
  }
  const byId = new Map(current.map((message) => [message.message_id, message]));
  for (const message of incoming) {
    byId.set(message.message_id, message);
  }
  return [...byId.values()].sort((left, right) => {
    const leftTime = new Date(left.created_at).getTime();
    const rightTime = new Date(right.created_at).getTime();
    return leftTime - rightTime;
  });
}

export function upsertOrchestratorStreamingMessage(
  current: OrchestratorMessage[],
  sessionId: string,
  assistantMessageId: string,
  sequence?: number,
): OrchestratorMessage[] {
  const existing = current.find((message) => message.message_id === assistantMessageId);
  if (existing) {
    return current.map((message) =>
      message.message_id === assistantMessageId
        ? {
            ...message,
            state: "streaming",
            blocks: message.blocks.length > 0 ? message.blocks : [{ type: "markdown", text: "" }],
          }
        : message,
    );
  }

  const createdAt = sequence == null ? new Date().toISOString() : new Date().toISOString();
  return [
    ...current,
    {
      message_id: assistantMessageId,
      session_id: sessionId,
      role: "assistant",
      state: "streaming",
      created_at: createdAt,
      blocks: [{ type: "markdown", text: "" }],
    },
  ];
}

export function appendOrchestratorDelta(
  current: OrchestratorMessage[],
  assistantMessageId: string,
  delta: string,
): OrchestratorMessage[] {
  return current.map((message) => {
    if (message.message_id !== assistantMessageId) {
      return message;
    }
    const blocks = [...message.blocks];
    const markdownIndex = blocks.findIndex((block) => block.type === "markdown");
    if (markdownIndex >= 0) {
      const currentText = blocks[markdownIndex].text ?? "";
      blocks[markdownIndex] = {
        ...blocks[markdownIndex],
        text: mergeStreamText(currentText, delta),
      };
    } else {
      blocks.unshift({ type: "markdown", text: delta });
    }
    return {
      ...message,
      state: "streaming",
      blocks,
    };
  });
}

export function finalizeOrchestratorMessage(
  current: OrchestratorMessage[],
  assistantMessageId: string,
  content: string,
  blocks: OrchestratorMessage["blocks"],
): OrchestratorMessage[] {
  const existing = current.find((message) => message.message_id === assistantMessageId);
  if (!existing) {
    return current;
  }
  return current.map((message) =>
    message.message_id === assistantMessageId
      ? {
          ...message,
          state: "completed",
          blocks:
            blocks.length > 0
              ? blocks
              : [{ type: "markdown", text: content }],
        }
      : message,
  );
}

export function markOrchestratorMessageFailed(
  current: OrchestratorMessage[],
  assistantMessageId: string,
): OrchestratorMessage[] {
  return current.map((message) =>
    message.message_id === assistantMessageId
      ? {
          ...message,
          state: "failed",
        }
      : message,
  );
}

function mergeStreamText(current: string, delta: string): string {
  if (!current) {
    return delta;
  }
  if (!delta) {
    return current;
  }
  if (delta.startsWith(current)) {
    return delta;
  }
  if (current.startsWith(delta) || current.includes(delta)) {
    return current;
  }
  const maxOverlap = Math.min(current.length, delta.length);
  for (let overlap = maxOverlap; overlap > 0; overlap -= 1) {
    if (current.slice(-overlap) === delta.slice(0, overlap)) {
      return `${current}${delta.slice(overlap)}`;
    }
  }
  return `${current}${delta}`;
}
