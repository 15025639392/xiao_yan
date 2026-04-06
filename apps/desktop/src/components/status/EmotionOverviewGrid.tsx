import type { EmotionState } from "../../lib/api";
import { getArousalLabel, getMoodValenceLabel } from "./emotionUtils";

type EmotionOverviewGridProps = {
  emotionState: EmotionState;
};

export function EmotionOverviewGrid({ emotionState }: EmotionOverviewGridProps) {
  return (
    <div
      className="emotion-grid"
      style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--space-2)", marginTop: "var(--space-3)" }}
    >
      <EmotionMetricCard label="情绪基调" value={getMoodValenceLabel(emotionState.mood_valence)} score={emotionState.mood_valence} />
      <EmotionMetricCard label="活跃度" value={getArousalLabel(emotionState.arousal)} score={emotionState.arousal} />
    </div>
  );
}

type EmotionMetricCardProps = {
  label: string;
  value: string;
  score: number;
};

function EmotionMetricCard({ label, value, score }: EmotionMetricCardProps) {
  return (
    <div
      className="emotion-card"
      style={{ padding: "var(--space-2)", background: "var(--bg-surface-elevated)", borderRadius: "var(--radius-md)" }}
    >
      <div style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", marginBottom: "var(--space-1)" }}>{label}</div>
      <div style={{ fontSize: "0.875rem", fontWeight: 500 }}>
        {value}
        <span style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", marginLeft: "var(--space-1)" }}>
          ({score.toFixed(1)})
        </span>
      </div>
    </div>
  );
}
