import { PersonaStatusBar } from "./persona/PersonaStatusBar";
import { PersonaWorkbench } from "./persona/PersonaWorkbench";
import { SurfaceCard } from "./ui";

type PersonaPanelProps = {
  onPersonaUpdated?: () => void;
  assistantName: string;
  petEnabled: boolean;
  petVisible: boolean;
  onSetPetEnabled: (enabled: boolean) => void;
};

export function PersonaPanel({
  onPersonaUpdated,
  assistantName,
  petEnabled,
  petVisible,
  onSetPetEnabled,
}: PersonaPanelProps) {
  return (
    <section className="persona-page">
      <header className="persona-page__header">
        <div className="persona-page__header-row">
          <div className="persona-page__title-group">
            <h2 className="persona-page__title">🎭 人格配置</h2>
            <p className="persona-page__subtitle">管理数字人的性格、风格与身份</p>
          </div>

          <div className="persona-page__feature">
            <SurfaceCard style={{ padding: "var(--space-2) var(--space-3)" }}>
              <div className="persona-feature-toggle">
                <div className="persona-feature-toggle__meta">
                  <div className="persona-feature-toggle__title">{assistantName}（小紫人）</div>
                  <div className="persona-feature-toggle__desc">
                    {petEnabled ? (petVisible ? "已启用" : "已启用（正在同步…）") : "已禁用（已退出）"}
                  </div>
                </div>
                <label className="persona-switch" aria-label="启用数字人形象（小紫人）">
                  <input
                    type="checkbox"
                    checked={petEnabled}
                    onChange={(e) => onSetPetEnabled(e.target.checked)}
                  />
                  <span className="persona-switch__track" />
                </label>
              </div>
            </SurfaceCard>
          </div>
        </div>
      </header>

      <PersonaStatusBar />

      <main className="persona-page__content">
        <PersonaWorkbench onUpdated={onPersonaUpdated} />
      </main>
    </section>
  );
}
