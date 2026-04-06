import { useCallback, useEffect, useState } from "react";
import type { ExpressionHabit, FormalLevel, PersonaProfile } from "../../lib/api";
import {
  fetchPersona,
  initializePersona,
  resetPersona,
  updatePersona,
  updatePersonality,
  updateSpeakingStyle,
} from "../../lib/api";
import type { PersonaSubTab } from "./personaConstants";
import { parseVerbalTics } from "./personaUtils";

type UsePersonaWorkbenchStateArgs = {
  onUpdated?: () => void;
};

export function usePersonaWorkbenchState({ onUpdated }: UsePersonaWorkbenchStateArgs) {
  const [profile, setProfile] = useState<PersonaProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<PersonaSubTab>("basic");

  const [name, setName] = useState("");
  const [identity, setIdentity] = useState("");
  const [originStory, setOriginStory] = useState("");

  const [openness, setOpenness] = useState(50);
  const [conscientiousness, setConscientiousness] = useState(50);
  const [extraversion, setExtraversion] = useState(50);
  const [agreeableness, setAgreeableness] = useState(50);
  const [neuroticism, setNeuroticism] = useState(50);

  const [formalLevel, setFormalLevel] = useState<FormalLevel>("neutral");
  const [expressionHabit, setExpressionHabit] = useState<ExpressionHabit>("direct");
  const [responseLength, setResponseLength] = useState("mixed");
  const [verbalTics, setVerbalTics] = useState("");

  const showToast = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 3000);
  }, []);

  const loadProfile = useCallback(async () => {
    try {
      setLoading(true);
      const profileData = await fetchPersona();
      setProfile(profileData);
      setName(profileData.name);
      setIdentity(profileData.identity);
      setOriginStory(profileData.origin_story);
      setOpenness(profileData.personality.openness);
      setConscientiousness(profileData.personality.conscientiousness);
      setExtraversion(profileData.personality.extraversion);
      setAgreeableness(profileData.personality.agreeableness);
      setNeuroticism(profileData.personality.neuroticism);
      setFormalLevel(profileData.speaking_style.formal_level);
      setExpressionHabit(profileData.speaking_style.expression_habit);
      setResponseLength(profileData.speaking_style.response_length);
      setVerbalTics(profileData.speaking_style.verbal_tics.join("、"));
    } catch (error) {
      showToast("加载失败: " + (error instanceof Error ? error.message : "?"));
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  const reload = useCallback(async () => {
    await loadProfile();
  }, [loadProfile]);

  const handleSaveBasic = useCallback(async () => {
    if (!profile) return;
    setSaving(true);
    try {
      await updatePersona({ name, identity, origin_story: originStory || undefined });
      showToast("基础信息已更新");
      onUpdated?.();
      await reload();
    } catch (error) {
      showToast("保存失败: " + (error instanceof Error ? error.message : "?"));
    } finally {
      setSaving(false);
    }
  }, [profile, name, identity, originStory, showToast, onUpdated, reload]);

  const handleSavePersonality = useCallback(async () => {
    if (!profile) return;
    setSaving(true);
    try {
      await updatePersonality({
        openness,
        conscientiousness,
        extraversion,
        agreeableness,
        neuroticism,
      });
      showToast("性格维度已更新");
      onUpdated?.();
      await reload();
    } catch (error) {
      showToast("保存失败: " + (error instanceof Error ? error.message : "?"));
    } finally {
      setSaving(false);
    }
  }, [profile, openness, conscientiousness, extraversion, agreeableness, neuroticism, showToast, onUpdated, reload]);

  const handleSaveStyle = useCallback(async () => {
    if (!profile) return;
    setSaving(true);
    try {
      await updateSpeakingStyle({
        formal_level: formalLevel,
        expression_habit: expressionHabit,
        response_length: responseLength,
        verbal_tics: parseVerbalTics(verbalTics),
      });
      showToast("说话风格已更新");
      onUpdated?.();
      await reload();
    } catch (error) {
      showToast("保存失败: " + (error instanceof Error ? error.message : "?"));
    } finally {
      setSaving(false);
    }
  }, [profile, formalLevel, expressionHabit, responseLength, verbalTics, showToast, onUpdated, reload]);

  const handleReset = useCallback(async () => {
    if (!window.confirm("确定要重置为默认人格吗？当前配置将丢失。")) return;
    setSaving(true);
    try {
      await resetPersona();
      showToast("已重置为默认人格");
      onUpdated?.();
      await reload();
    } catch (error) {
      showToast("重置失败: " + (error instanceof Error ? error.message : "?"));
    } finally {
      setSaving(false);
    }
  }, [showToast, onUpdated, reload]);

  const handleInitialize = useCallback(async () => {
    if (
      !window.confirm(
        "确定要初始化数字人吗？\n\n这将清空所有记忆、目标和状态，并将数字人恢复到初始状态。\n\n此操作不可撤销！",
      )
    ) {
      return;
    }
    setSaving(true);
    try {
      const result = await initializePersona();
      showToast(`${result.message}（已清空 ${result.cleared.memories} 条记忆和 ${result.cleared.goals} 个目标）`);
      onUpdated?.();
      await reload();
    } catch (error) {
      showToast("初始化失败: " + (error instanceof Error ? error.message : "?"));
    } finally {
      setSaving(false);
    }
  }, [showToast, onUpdated, reload]);

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  return {
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
  };
}
