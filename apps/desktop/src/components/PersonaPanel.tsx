import { PersonaStatusBar } from "./persona/PersonaStatusBar";
import { PersonaWorkbench } from "./persona/PersonaWorkbench";

type PersonaPanelProps = {
  onPersonaUpdated?: () => void;
};

export function PersonaPanel({ onPersonaUpdated }: PersonaPanelProps) {
  return (
    <section className="persona-page">
      <header className="persona-page__header">
        <div className="persona-page__title-group">
          <h2 className="persona-page__title">🎭 人格配置</h2>
          <p className="persona-page__subtitle">管理数字人的性格、风格与身份</p>
        </div>
      </header>

      <PersonaStatusBar />

      <main className="persona-page__content">
        <PersonaWorkbench onUpdated={onPersonaUpdated} />
      </main>
    </section>
  );
}

