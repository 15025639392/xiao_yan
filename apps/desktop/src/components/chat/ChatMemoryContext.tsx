import type { MemoryEntryDisplay } from "../../lib/api";
import { formatRelativeDate, getKindLabel, getStrengthLabel } from "./chatUtils";

type ChatMemoryContextProps = {
  memories: MemoryEntryDisplay[];
  isExpanded: boolean;
  onToggle: () => void;
};

export function ChatMemoryContext({ memories, isExpanded, onToggle }: ChatMemoryContextProps) {
  return (
    <div className="chat-message__memory-context">
      <button type="button" className="chat-message__memory-toggle" onClick={onToggle}>
        <span className="chat-message__memory-icon">📚</span>
        <span className="chat-message__memory-label">相关记忆 ({memories.length})</span>
        <span className={`chat-message__memory-chevron ${isExpanded ? "chat-message__memory-chevron--expanded" : ""}`}>
          ▼
        </span>
      </button>

      {isExpanded ? (
        <div className="chat-message__memory-list">
          {memories.map((memory) => (
            <div key={memory.id} className="chat-message__memory-item">
              <div className="chat-message__memory-header">
                <span className={`chat-message__memory-kind chat-message__memory-kind--${memory.kind}`}>
                  {getKindLabel(memory.kind)}
                </span>
                {memory.starred ? <span className="chat-message__memory-starred">⭐</span> : null}
              </div>
              <p className="chat-message__memory-content">{memory.content}</p>
              <div className="chat-message__memory-footer">
                <span className={`chat-message__memory-strength chat-message__memory-strength--${memory.strength}`}>
                  {getStrengthLabel(memory.strength)}
                </span>
                {memory.created_at ? (
                  <span className="chat-message__memory-date">{formatRelativeDate(memory.created_at)}</span>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

