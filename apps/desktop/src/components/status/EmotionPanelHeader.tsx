import type { EmotionState } from "../../lib/api";
import { getEmotionBgColor, getEmotionIcon, getEmotionLabel } from "./emotionUtils";

type EmotionPanelHeaderProps = {
  emotionState: EmotionState;
  showDetails: boolean;
  onToggleDetails: () => void;
};

export function EmotionPanelHeader({ emotionState, showDetails, onToggleDetails }: EmotionPanelHeaderProps) {
  return (
    <div
      className="emotion-panel__header"
      onClick={onToggleDetails}
      style={{ cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between" }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <span className="emotion-panel__icon">{getEmotionIcon(emotionState.primary_emotion)}</span>
        <h3 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600 }}>情绪状态</h3>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <span className="emotion-badge" style={{ background: getEmotionBgColor(emotionState.primary_emotion) }}>
          {getEmotionLabel(emotionState.primary_emotion)}
        </span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          style={{ transform: showDetails ? "rotate(180deg)" : "rotate(0)", transition: "transform 200ms ease" }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
    </div>
  );
}
