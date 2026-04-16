import type { InnerWorldState } from "../lib/api";
import { EmptyState } from "./ui/EmptyState";
import { Panel } from "./ui/Panel";
import { renderFocusStage, renderMood, renderScale, renderTimeOfDay } from "./world/worldUtils";

type WorldPanelProps = {
  world: InnerWorldState | null;
};

export function WorldPanel({ world }: WorldPanelProps) {
  return (
    <Panel icon="🌊" title="内在世界" subtitle="心境信号">
      {world ? (
        <div className="metric-grid">
          <div className="metric-card">
            <p className="metric-card__label">时间感</p>
            <p className="metric-card__value">{renderTimeOfDay(world.time_of_day)}</p>
          </div>
          <div className="metric-card">
            <p className="metric-card__label">能量</p>
            <p className="metric-card__value">{renderScale(world.energy)}</p>
          </div>
          <div className="metric-card">
            <p className="metric-card__label">情绪</p>
            <p className="metric-card__value">{renderMood(world.mood)}</p>
          </div>
          <div className="metric-card">
            <p className="metric-card__label">专注张力</p>
            <p className="metric-card__value">{renderScale(world.focus_tension)}</p>
          </div>
          {world.focus_stage && world.focus_stage !== "none" ? (
            <div className="metric-card">
              <p className="metric-card__label">当前阶段</p>
              <p className="metric-card__value">{renderFocusStage(world.focus_stage)}</p>
            </div>
          ) : null}
          {world.focus_step ? (
            <div className="metric-card">
              <p className="metric-card__label">当前步骤</p>
              <p className="metric-card__value">第 {world.focus_step} 步</p>
            </div>
          ) : null}
        </div>
      ) : (
        <EmptyState size="small">
          <p>内在状态加载中。</p>
        </EmptyState>
      )}
    </Panel>
  );
}
