import type { RelationshipSummary } from "../../lib/api";

type MemoryRelationshipSummaryProps = {
  relationship: RelationshipSummary | null;
};

export function MemoryRelationshipSummary({ relationship }: MemoryRelationshipSummaryProps) {
  if (!relationship || !relationship.available) {
    return null;
  }

  const groups = [
    { label: "相处边界", items: relationship.boundaries, tone: "boundary" },
    { label: "对用户承诺", items: relationship.commitments, tone: "commitment" },
    { label: "用户偏好", items: relationship.preferences, tone: "preference" },
  ].filter((group) => group.items.length > 0);

  if (groups.length === 0) {
    return null;
  }

  return (
    <section className="memory-relationship" aria-label="关系状态">
      <div className="memory-relationship__header">
        <span className="memory-relationship__title">关系状态</span>
        <span className="memory-relationship__hint">这不是普通记忆，而是当前相处方式的稳定摘要。</span>
      </div>

      <div className="memory-relationship__groups">
        {groups.map((group) => (
          <section
            key={group.label}
            className={`memory-relationship__group memory-relationship__group--${group.tone}`}
          >
            <h3 className="memory-relationship__group-title">{group.label}</h3>
            <ul className="memory-relationship__list">
              {group.items.map((item) => (
                <li key={item} className="memory-relationship__item">
                  {item}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </section>
  );
}
