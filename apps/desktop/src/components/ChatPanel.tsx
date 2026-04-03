export type ChatEntry = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type ChatPanelProps = {
  draft: string;
  messages: ChatEntry[];
  isSending: boolean;
  onDraftChange: (value: string) => void;
  onSend: () => void;
};

export function ChatPanel({
  draft,
  messages,
  isSending,
  onDraftChange,
  onSend,
}: ChatPanelProps) {
  return (
    <section>
      <div>
        {messages.map((message) => (
          <p key={message.id}>
            {message.role === "user" ? "You" : "Xiao Yan"}: {message.content}
          </p>
        ))}
      </div>
      <label>
        Chat Input
        <input
          type="text"
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
        />
      </label>
      <button onClick={onSend} type="button" disabled={isSending || !draft.trim()}>
        {isSending ? "Sending..." : "Send"}
      </button>
    </section>
  );
}
