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
    <section className="panel panel--console">
      <div className="panel__header">
        <div>
          <p className="panel__eyebrow">实时交互</p>
          <h2 className="panel__title">对话控制台</h2>
        </div>
        <span className="status-badge">{isSending ? "正在回复" : "在线中"}</span>
      </div>
      <p className="panel__subtitle">她会结合当前状态、计划和记忆来回应你。</p>
      <div className="chat-thread">
        {messages.length === 0 ? (
          <p className="empty-state">尚无对话记录。</p>
        ) : (
          messages.map((message) => (
            <article
              key={message.id}
              className={`chat-bubble chat-bubble--${message.role === "user" ? "user" : "assistant"}`}
            >
              <p className="chat-bubble__speaker">{message.role === "user" ? "你" : "小晏"}</p>
              <p className="chat-bubble__content">{message.content}</p>
            </article>
          ))
        )}
      </div>
      <div className="chat-composer">
        <label className="sr-only" htmlFor="chat-input">
          对话输入
        </label>
        <input
          id="chat-input"
          aria-label="对话输入"
          className="chat-composer__input"
          type="text"
          value={draft}
          placeholder="想和小晏说些什么？"
          onChange={(event) => onDraftChange(event.target.value)}
        />
        <button
          className="soft-button soft-button--primary"
          onClick={onSend}
          type="button"
          disabled={isSending || !draft.trim()}
        >
          {isSending ? "发送中" : "发送"}
        </button>
      </div>
      <p className="chat-composer__hint">
        {isSending ? "小晏正在整理回复。" : "输入后点击发送。"}
      </p>
    </section>
  );
}
