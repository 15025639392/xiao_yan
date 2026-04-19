import type { MemoryReference } from "./chatTypes";

type ChatMemoryReferenceContextProps = {
  references: MemoryReference[];
  isExpanded: boolean;
  onToggle: () => void;
};

export function ChatMemoryReferenceContext({
  references,
  isExpanded,
  onToggle,
}: ChatMemoryReferenceContextProps) {
  return (
    <div className="chat-message__knowledge-context">
      <button
        type="button"
        className="chat-message__knowledge-toggle"
        onClick={onToggle}
        aria-label={`回复来源 (${references.length})`}
      >
        <span className="chat-message__knowledge-icon">🗂️</span>
        <span className="chat-message__knowledge-label">回复来源 ({references.length})</span>
        <span
          className={`chat-message__knowledge-chevron ${isExpanded ? "chat-message__knowledge-chevron--expanded" : ""}`}
        >
          ▼
        </span>
      </button>

      {isExpanded ? (
        <div className="chat-message__knowledge-references" aria-label="记忆来源">
          <span className="chat-message__knowledge-title">记忆来源</span>
          <ul className="chat-message__knowledge-list">
            {references.map((reference, index) => (
              <li key={`memory-reference-${index}`} className="chat-message__knowledge-item">
                <div className="chat-message__knowledge-head">
                  <span className="chat-message__knowledge-source">{reference.source}</span>
                  {typeof reference.similarity === "number" ? (
                    <span className="chat-message__knowledge-score">相似度 {reference.similarity.toFixed(2)}</span>
                  ) : null}
                </div>
                <span className="chat-message__knowledge-excerpt">{reference.excerpt}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
