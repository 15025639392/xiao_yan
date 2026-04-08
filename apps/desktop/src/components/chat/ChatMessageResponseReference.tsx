import type { RelationshipSummary } from "../../lib/api";

type ChatMessageResponseReferenceProps = {
  relationship: RelationshipSummary | null;
};

export function ChatMessageResponseReference({ relationship }: ChatMessageResponseReferenceProps) {
  if (!relationship || !relationship.available) {
    return null;
  }

  const primaryReference =
    (relationship.boundaries[0] && { label: "先守住边界", content: relationship.boundaries[0] }) ||
    (relationship.commitments[0] && { label: "先兑现承诺", content: relationship.commitments[0] }) ||
    (relationship.preferences[0] && { label: "尽量贴合偏好", content: relationship.preferences[0] }) ||
    null;

  if (!primaryReference) {
    return null;
  }

  return (
    <div className="chat-message__reference" aria-label="本次回应参考">
      <span className="chat-message__reference-title">本次回应参考</span>
      <span className="chat-message__reference-label">{primaryReference.label}</span>
      <span className="chat-message__reference-content">{primaryReference.content}</span>
    </div>
  );
}
