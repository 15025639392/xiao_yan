import type { EmotionState } from "../../lib/api";
import { getEmotionBorderColor, getEmotionIcon, getEmotionLabel, getIntensityLabel } from "./emotionUtils";

type EmotionActiveEntriesProps = {
  emotionState: EmotionState;
};

export function EmotionActiveEntries({ emotionState }: EmotionActiveEntriesProps) {
  if (emotionState.active_entries.length === 0) {
    return null;
  }

  return (
    <div style={{ marginTop: "var(--space-3)" }}>
      <h4 style={{ margin: "0 0 var(--space-2)", fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
        活跃情绪 ({emotionState.active_entry_count})
      </h4>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        {emotionState.active_entries.slice(0, 3).map((entry, index) => (
          <div
            key={index}
            style={{
              padding: "var(--space-2)",
              background: "var(--bg-surface-elevated)",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.8125rem",
              borderLeft: `2px solid ${getEmotionBorderColor(entry.emotion_type)}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-1)" }}>
              <span>{getEmotionIcon(entry.emotion_type)}</span>
              <span style={{ fontWeight: 500 }}>{getEmotionLabel(entry.emotion_type)}</span>
              <span style={{ fontSize: "0.75rem", color: "var(--text-tertiary)" }}>{getIntensityLabel(entry.intensity)}</span>
            </div>
            <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>{entry.reason}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
