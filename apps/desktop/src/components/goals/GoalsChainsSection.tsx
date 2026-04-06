import type { GoalChainGroup } from "./goalsUtils";

type GoalsChainsSectionProps = {
  chainedGroups: GoalChainGroup[];
};

export function GoalsChainsSection({ chainedGroups }: GoalsChainsSectionProps) {
  if (chainedGroups.length === 0) {
    return null;
  }

  return (
    <section style={{ marginBottom: "var(--space-6)" }}>
      <h3 style={{ margin: "0 0 var(--space-4)", fontSize: "0.875rem", color: "var(--text-secondary)" }}>目标链</h3>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "var(--space-3)",
        }}
      >
        {chainedGroups.map((group) => (
          <article
            key={group.chainId}
            style={{
              padding: "var(--space-4)",
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <h4 style={{ margin: "0 0 var(--space-2)", fontSize: "0.9375rem" }}>链路 {group.chainId}</h4>
            <p
              style={{
                margin: 0,
                fontSize: "0.8125rem",
                color: "var(--text-tertiary)",
                lineHeight: 1.5,
              }}
            >
              {group.summary}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
