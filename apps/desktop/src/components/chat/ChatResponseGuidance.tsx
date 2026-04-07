import type { RelationshipSummary } from "../../lib/api";

type ChatResponseGuidanceProps = {
  relationship: RelationshipSummary | null;
};

export function ChatResponseGuidance({ relationship }: ChatResponseGuidanceProps) {
  if (!relationship || !relationship.available) {
    return null;
  }

  const principles = [
    {
      label: "先守住边界",
      content: relationship.boundaries[0],
    },
    {
      label: "先兑现承诺",
      content: relationship.commitments[0],
    },
    {
      label: "尽量贴合偏好",
      content: relationship.preferences[0],
    },
  ].filter((item): item is { label: string; content: string } => Boolean(item.content));

  if (principles.length === 0) {
    return null;
  }

  return (
    <section className="chat-guidance" aria-label="本次回应原则">
      <div className="chat-guidance__header">
        <span className="chat-guidance__title">本次回应原则</span>
        <span className="chat-guidance__hint">把关系记忆转成这次回复前的即时约束。</span>
      </div>

      <div className="chat-guidance__items">
        {principles.map((item) => (
          <div key={item.label} className="chat-guidance__item">
            <span className="chat-guidance__label">{item.label}</span>
            <span className="chat-guidance__content">{item.content}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
