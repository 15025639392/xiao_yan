import type { EmotionState } from "../../lib/api";
import { getEmotionIcon, getEmotionLabel, getIntensityLabel } from "./emotionUtils";

type EmotionPrimarySectionProps = {
  emotionState: EmotionState;
};

export function EmotionPrimarySection({ emotionState }: EmotionPrimarySectionProps) {
  return (
    <div className="emotion-section">
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
        <span className="emotion-icon--primary">{getEmotionIcon(emotionState.primary_emotion)}</span>
        <span style={{ fontSize: "0.875rem", fontWeight: 500 }}>
          主要情绪: {getEmotionLabel(emotionState.primary_emotion)}
        </span>
        <span
          className="intensity-badge"
          style={{ fontSize: "0.75rem", padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius-full)" }}
        >
          {getIntensityLabel(emotionState.primary_intensity)}
        </span>
      </div>

      {emotionState.secondary_emotion ? (
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
          <span className="emotion-icon--secondary">{getEmotionIcon(emotionState.secondary_emotion)}</span>
          <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
            次要情绪: {getEmotionLabel(emotionState.secondary_emotion)}
          </span>
          <span
            className="intensity-badge"
            style={{
              fontSize: "0.75rem",
              padding: "var(--space-1) var(--space-2)",
              borderRadius: "var(--radius-full)",
              opacity: 0.8,
            }}
          >
            {getIntensityLabel(emotionState.secondary_intensity)}
          </span>
        </div>
      ) : null}
    </div>
  );
}
