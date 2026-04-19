import type { InnerWorldState } from "../lib/api";
import { EmptyState } from "./ui/EmptyState";
import { Panel } from "./ui/Panel";
import { renderFocusStage, renderMood, renderScale, renderTimeOfDay } from "./world/worldUtils";

type WorldPanelProps = {
  world: InnerWorldState | null;
};

export function WorldPanel({ world }: WorldPanelProps) {
  return (
    <Panel icon="🌊" title="此刻感受" subtitle="先看她当下怎么在活着">
      {world ? (
        <div style={{ display: "grid", gap: "var(--space-3)" }}>
          <p style={worldCopyStyle}>
            {world.latest_event?.trim() || buildWorldSummary(world)}
          </p>
          {world.focus_stage && world.focus_stage !== "none" ? (
            <p style={worldCopyStyle}>
              现在在{renderFocusStage(world.focus_stage)}
              {world.focus_step ? `，已经走到第 ${world.focus_step} 步。` : "。"}
            </p>
          ) : world.focus_step ? (
            <p style={worldCopyStyle}>已经走到第 {world.focus_step} 步。</p>
          ) : null}
        </div>
      ) : (
        <EmptyState size="small">
          <p>此刻感受加载中。</p>
        </EmptyState>
      )}
    </Panel>
  );
}

const worldCopyStyle = {
  margin: 0,
  color: "var(--text-secondary)",
  fontSize: "0.875rem",
  lineHeight: 1.6,
} as const;

function buildWorldSummary(world: InnerWorldState): string {
  const focusStage =
    world.focus_stage && world.focus_stage !== "none" ? `，现在在${renderFocusStage(world.focus_stage)}` : "";
  const focusStep = world.focus_step ? `，已经走到第 ${world.focus_step} 步` : "";
  return `${renderTimeOfDay(world.time_of_day)}里，她的能量${renderScale(world.energy)}、情绪偏${renderMood(world.mood)}${focusStage}${focusStep}。`;
}
