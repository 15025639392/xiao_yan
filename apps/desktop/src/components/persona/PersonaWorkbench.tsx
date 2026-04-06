import { PersonaBasicTab } from "./PersonaBasicTab";
import { PersonaPersonalityTab } from "./PersonaPersonalityTab";
import { PersonaSubTabs } from "./PersonaSubTabs";
import { PersonaStyleTab } from "./PersonaStyleTab";
import { PersonaWorkbenchSkeleton } from "./PersonaWorkbenchSkeleton";
import { usePersonaWorkbenchState } from "./usePersonaWorkbench";

type PersonaWorkbenchProps = {
  onUpdated?: () => void;
};

export function PersonaWorkbench({ onUpdated }: PersonaWorkbenchProps) {
  const {
    loading,
    saving,
    toast,
    activeSubTab,
    setActiveSubTab,
    name,
    setName,
    identity,
    setIdentity,
    originStory,
    setOriginStory,
    openness,
    setOpenness,
    conscientiousness,
    setConscientiousness,
    extraversion,
    setExtraversion,
    agreeableness,
    setAgreeableness,
    neuroticism,
    setNeuroticism,
    formalLevel,
    setFormalLevel,
    expressionHabit,
    setExpressionHabit,
    responseLength,
    setResponseLength,
    verbalTics,
    setVerbalTics,
    handleSaveBasic,
    handleSavePersonality,
    handleSaveStyle,
    handleReset,
    handleInitialize,
  } = usePersonaWorkbenchState({ onUpdated });

  if (loading) {
    return <PersonaWorkbenchSkeleton />;
  }

  return (
    <div className="persona-config-panel">
      <PersonaSubTabs activeSubTab={activeSubTab} toast={toast} onChange={setActiveSubTab} />

      <div className="persona-config-body">
        {activeSubTab === "basic" ? (
          <PersonaBasicTab
            name={name}
            identity={identity}
            originStory={originStory}
            saving={saving}
            onNameChange={setName}
            onIdentityChange={setIdentity}
            onOriginStoryChange={setOriginStory}
            onSave={handleSaveBasic}
            onReset={handleReset}
            onInitialize={handleInitialize}
          />
        ) : null}

        {activeSubTab === "personality" ? (
          <PersonaPersonalityTab
            openness={openness}
            conscientiousness={conscientiousness}
            extraversion={extraversion}
            agreeableness={agreeableness}
            neuroticism={neuroticism}
            saving={saving}
            onOpennessChange={setOpenness}
            onConscientiousnessChange={setConscientiousness}
            onExtraversionChange={setExtraversion}
            onAgreeablenessChange={setAgreeableness}
            onNeuroticismChange={setNeuroticism}
            onSave={handleSavePersonality}
          />
        ) : null}

        {activeSubTab === "style" ? (
          <PersonaStyleTab
            formalLevel={formalLevel}
            expressionHabit={expressionHabit}
            responseLength={responseLength}
            verbalTics={verbalTics}
            saving={saving}
            onFormalLevelChange={setFormalLevel}
            onExpressionHabitChange={setExpressionHabit}
            onResponseLengthChange={setResponseLength}
            onVerbalTicsChange={setVerbalTics}
            onSave={handleSaveStyle}
          />
        ) : null}
      </div>
    </div>
  );
}
