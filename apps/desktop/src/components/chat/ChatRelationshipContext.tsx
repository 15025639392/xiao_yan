import type { RelationshipSummary } from "../../lib/api";

type ChatRelationshipContextProps = {
  relationship: RelationshipSummary | null;
};

export function ChatRelationshipContext({ relationship }: ChatRelationshipContextProps) {
  if (!relationship || !relationship.available) {
    return null;
  }

  const groups = [
    { label: "边界", items: relationship.boundaries },
    { label: "承诺", items: relationship.commitments },
    { label: "偏好", items: relationship.preferences },
  ].filter((group) => group.items.length > 0);

  if (groups.length === 0) {
    return null;
  }

  return (
    <section className="chat-relationship" aria-label="当前相处语境">
      <div className="chat-relationship__header">
        <span className="chat-relationship__title">当前相处语境</span>
        <span className="chat-relationship__hint">回应前先尊重这些已经形成的相处方式。</span>
      </div>

      <div className="chat-relationship__groups">
        {groups.map((group) => (
          <div key={group.label} className="chat-relationship__group">
            <span className="chat-relationship__label">{group.label}</span>
            <div className="chat-relationship__items">
              {group.items.map((item) => (
                <span key={item} className="chat-relationship__item">
                  {item}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
