export type PendingChatRequest = {
  message: string;
  requestKey: string;
};

export function createChatRequestKey(): string {
  return `chat-request-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
