import { PersonaStatusBar } from "./persona/PersonaStatusBar";
import { PersonaWorkbench } from "./persona/PersonaWorkbench";
import { SurfaceCard } from "./ui";

type PersonaPanelProps = {
  onPersonaUpdated?: () => void;
  assistantName: string;
  avatarEnabled: boolean;
  onSetAvatarEnabled: (enabled: boolean) => void;
};

export function PersonaPanel({
  onPersonaUpdated,
  assistantName,
  avatarEnabled,
  onSetAvatarEnabled,
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
                  <div className="persona-feature-toggle__title">{assistantName}（VRM 外显）</div>
                  <div className="persona-feature-toggle__desc">
                    {avatarEnabled ? "已启用（右下角独立 VRM 窗口）" : "已禁用"}
                  </div>
                </div>
                <label className="persona-switch" aria-label="启用 VRM 外显模型">
                  <input
                    type="checkbox"
                    checked={avatarEnabled}
                    onChange={(e) => onSetAvatarEnabled(e.target.checked)}
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
