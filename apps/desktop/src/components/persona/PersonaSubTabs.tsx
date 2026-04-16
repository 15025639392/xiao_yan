import { Tabs, TabsList, TabsTrigger } from "../ui";
import { PERSONA_SUB_TABS, type PersonaSubTab } from "./personaConstants";

type PersonaSubTabsProps = {
  activeSubTab: PersonaSubTab;
  toast: string | null;
  onChange: (tab: PersonaSubTab) => void;
};

export function PersonaSubTabs({ activeSubTab, toast, onChange }: PersonaSubTabsProps) {
  return (
    <Tabs value={activeSubTab} onValueChange={(value) => onChange(value as PersonaSubTab)}>
      <TabsList className="persona-config-tabs">
        {PERSONA_SUB_TABS.map((tab) => (
          <TabsTrigger
            key={tab.id}
            value={tab.id}
            className={`persona-config-tab ${activeSubTab === tab.id ? "persona-config-tab--active" : ""}`}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </TabsTrigger>
        ))}
        {toast ? <span className="persona-config-toast">{toast}</span> : null}
      </TabsList>
    </Tabs>
  );
}
