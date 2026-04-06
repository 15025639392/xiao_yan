import { PERSONA_SUB_TABS, type PersonaSubTab } from "./personaConstants";

type PersonaSubTabsProps = {
  activeSubTab: PersonaSubTab;
  toast: string | null;
  onChange: (tab: PersonaSubTab) => void;
};

export function PersonaSubTabs({ activeSubTab, toast, onChange }: PersonaSubTabsProps) {
  return (
    <div className="persona-config-tabs">
      {PERSONA_SUB_TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`persona-config-tab ${activeSubTab === tab.id ? "persona-config-tab--active" : ""}`}
          onClick={() => onChange(tab.id)}
        >
          <span>{tab.icon}</span>
          <span>{tab.label}</span>
        </button>
      ))}
      {toast ? <span className="persona-config-toast">{toast}</span> : null}
    </div>
  );
}
