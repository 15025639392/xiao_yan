import type { EmotionState } from "../../lib/api";
import { EmotionActiveEntries } from "./EmotionActiveEntries";
import { EmotionOverviewGrid } from "./EmotionOverviewGrid";
import { EmotionPanelHeader } from "./EmotionPanelHeader";
import { EmotionPrimarySection } from "./EmotionPrimarySection";
import { EmotionUpdatedAt } from "./EmotionUpdatedAt";

type EmotionPanelProps = {
  emotionState: EmotionState;
  showDetails: boolean;
  onToggleDetails: () => void;
};

export function EmotionPanel({ emotionState, showDetails, onToggleDetails }: EmotionPanelProps) {
  return (
    <section className="emotion-panel" style={{ marginTop: "var(--space-5)" }}>
      <EmotionPanelHeader emotionState={emotionState} showDetails={showDetails} onToggleDetails={onToggleDetails} />

      {showDetails ? (
        <div className="emotion-panel__body">
          <EmotionPrimarySection emotionState={emotionState} />
          <EmotionOverviewGrid emotionState={emotionState} />
          <EmotionActiveEntries emotionState={emotionState} />
          <EmotionUpdatedAt lastUpdated={emotionState.last_updated} />
        </div>
      ) : null}
    </section>
  );
}
