import { useState, useEffect } from "react";
import type {
  PersonaProfile,
  FormalLevel,
  ExpressionHabit,
} from "../lib/api";
import {
  fetchPersona,
  fetchEmotionState,
  updatePersona,
  updatePersonality,
  updateSpeakingStyle,
  resetPersona,
} from "../lib/api";

type SettingsPanelProps = {
  onPersonaUpdated?: () => void;
};

// ═══════════════════════════════════════════════════
// 人格工作台 - 完整的人格管理中心
// ═══════════════════════════════════════════════════

export function SettingsPanel({ onPersonaUpdated }: SettingsPanelProps) {
  return (
    <section className="persona-page">
      {/* 页面头部 */}
      <header className="persona-page__header">
        <div className="persona-page__title-group">
          <h2 className="persona-page__title">🎭 人格配置</h2>
          <p className="persona-page__subtitle">管理数字人的性格、风格与身份</p>
        </div>
      </header>

      {/* 状态概览条 */}
      <PersonaStatusBar />

      {/* 配置内容区 */}
      <main className="persona-page__content">
        <PersonaWorkbench onUpdated={onPersonaUpdated} />
      </main>
    </section>
  );
}

// ═══════════════════════════════════════════════════
// 人格状态概览条 - 横向精简展示
// ═══════════════════════════════════════════════════

function PersonaStatusBar() {
  const [profile, setProfile] = useState<PersonaProfile | null>(null);
  const [emotion, setEmotion] = useState<{
    primary_emotion: string;
    primary_intensity: string;
    mood_valence: number;
  } | null>(null);

  useEffect(() => {
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  async function load() {
    try {
      const [p, e] = await Promise.all([fetchPersona(), fetchEmotionState()]);
      setProfile(p);
      setEmotion(e);
    } catch {
      // 静默失败
    }
  }

  if (!profile || !emotion) {
    return (
      <div className="persona-status-bar persona-status-bar--loading">
        <div className="persona-status-bar__skeleton" />
      </div>
    );
  }

  const emotionConfig = getEmotionDisplay(emotion.primary_emotion, emotion.primary_intensity);
  const moodPercent = ((emotion.mood_valence + 1) / 2) * 100;

  return (
    <div className="persona-status-bar">
      <div className="persona-status-bar__item">
        <span className="persona-status-bar__label">名字</span>
        <span className="persona-status-bar__value">{profile.name}</span>
      </div>
      <div className="persona-status-bar__divider" />
      <div className="persona-status-bar__item">
        <span className="persona-status-bar__label">身份</span>
        <span className="persona-status-bar__value">{profile.identity}</span>
      </div>
      <div className="persona-status-bar__divider" />
      <div className="persona-status-bar__item">
        <span className="persona-status-bar__label">当前情绪</span>
        <span 
          className="persona-status-bar__emotion"
          style={{ 
            color: emotionConfig.color,
            borderColor: emotionConfig.color 
          }}
        >
          {emotionConfig.emoji} {emotionConfig.label}
        </span>
      </div>
      <div className="persona-status-bar__divider" />
      <div className="persona-status-bar__item persona-status-bar__item--grow">
        <span className="persona-status-bar__label">心情值</span>
        <div className="persona-status-bar__mood">
          <div className="persona-status-bar__mood-track">
            <div 
              className="persona-status-bar__mood-fill"
              style={{ 
                width: `${moodPercent}%`,
                background: moodPercent > 60 ? 'var(--success)' : moodPercent > 40 ? 'var(--warning)' : 'var(--danger)'
              }}
            />
          </div>
          <span className="persona-status-bar__mood-value">{emotion.mood_valence.toFixed(1)}</span>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════
// 人格配置工作台
// ═══════════════════════════════════════════════════

// ═══════════════════════════════════════════════════
// 情绪显示辅助函数
// ═══════════════════════════════════════════════════

function getEmotionDisplay(emotion: string, intensity: string): {
  emoji: string;
  label: string;
  color: string;
} {
  const map: Record<string, { emoji: string; label: string; color: string }> = {
    joy: { emoji: "😊", label: "开心", color: "#10b981" },
    sadness: { emoji: "😢", label: "难过", color: "#6b7280" },
    anger: { emoji: "😠", label: "生气", color: "#ef4444" },
    fear: { emoji: "😨", label: "害怕", color: "#8b5cf6" },
    surprise: { emoji: "😲", label: "惊讶", color: "#f59e0b" },
    disgust: { emoji: "🤢", label: "厌恶", color: "#84cc16" },
    calm: { emoji: "😌", label: "平静", color: "#3b82f6" },
    lonely: { emoji: "🥺", label: "孤独", color: "#6366f1" },
    grateful: { emoji: "🙏", label: "感激", color: "#ec4899" },
    frustrated: { emoji: "😤", label: "沮丧", color: "#f97316" },
    proud: { emoji: "😎", label: "自豪", color: "#14b8a6" },
    engaged: { emoji: "🤔", label: "专注", color: "#0ea5e9" },
  };
  return map[emotion] || { emoji: "😐", label: emotion, color: "#9ca3af" };
}

// ═══════════════════════════════════════════════════
// 人格配置工作台
// ═══════════════════════════════════════════════════

function PersonaWorkbench({ onUpdated }: { onUpdated?: () => void }) {
  const [profile, setProfile] = useState<PersonaProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<"basic" | "personality" | "style">("basic");

  // 编辑状态
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

  useEffect(() => { load(); }, []);

  async function load() {
    try {
      setLoading(true);
      const p = await fetchPersona();
      setProfile(p);
      setName(p.name);
      setIdentity(p.identity);
      setOriginStory(p.origin_story);
      setOpenness(p.personality.openness);
      setConscientiousness(p.personality.conscientiousness);
      setExtraversion(p.personality.extraversion);
      setAgreeableness(p.personality.agreeableness);
      setNeuroticism(p.personality.neuroticism);
      setFormalLevel(p.speaking_style.formal_level);
      setExpressionHabit(p.speaking_style.expression_habit);
      setResponseLength(p.speaking_style.response_length);
      setVerbalTics(p.speaking_style.verbal_tics.join("、"));
    } catch (e) {
      showToast("加载失败: " + (e instanceof Error ? e.message : "?"));
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveBasic() {
    if (!profile) return;
    setSaving(true);
    try {
      await updatePersona({ name, identity, origin_story: originStory || undefined });
      showToast("基础信息已更新");
      onUpdated?.();
      await load();
    } catch (e) {
      showToast("保存失败: " + (e instanceof Error ? e.message : "?"));
    } finally {
      setSaving(false);
    }
  }

  async function handleSavePersonality() {
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
      await load();
    } catch (e) {
      showToast("保存失败: " + (e instanceof Error ? e.message : "?"));
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveStyle() {
    if (!profile) return;
    setSaving(true);
    try {
      await updateSpeakingStyle({
        formal_level: formalLevel,
        expression_habit: expressionHabit,
        response_length: responseLength,
        verbal_tics: verbalTics ? verbalTics.split(/[,，、]/).map((s) => s.trim()).filter(Boolean) : undefined,
      });
      showToast("说话风格已更新");
      onUpdated?.();
      await load();
    } catch (e) {
      showToast("保存失败: " + (e instanceof Error ? e.message : "?"));
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    if (!confirm("确定要重置为默认人格吗？当前配置将丢失。")) return;
    setSaving(true);
    try {
      await resetPersona();
      showToast("已重置为默认人格");
      onUpdated?.();
      await load();
    } catch (e) {
      showToast("重置失败: " + (e instanceof Error ? e.message : "?"));
    } finally {
      setSaving(false);
    }
  }

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  }

  if (loading) {
    return <PersonaWorkbenchSkeleton />;
  }

  const subTabs = [
    { id: "basic" as const, label: "基础信息", icon: "👤" },
    { id: "personality" as const, label: "性格维度", icon: "🧬" },
    { id: "style" as const, label: "说话风格", icon: "💬" },
  ];

  return (
    <div className="persona-config-panel">
      {/* 子标签切换 */}
      <div className="persona-config-tabs">
        {subTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`persona-config-tab ${activeSubTab === tab.id ? "persona-config-tab--active" : ""}`}
            onClick={() => setActiveSubTab(tab.id)}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
        {toast && <span className="persona-config-toast">{toast}</span>}
      </div>

      {/* 内容区域 */}
      <div className="persona-config-body">
        {activeSubTab === "basic" && (
          <div className="persona-form">
            <div className="persona-form__section">
              <h4 className="persona-form__section-title">身份信息</h4>
              
              <div className="persona-form__field">
                <label className="persona-form__label" htmlFor="wb-persona-name">
                  名字
                  <span className="persona-form__hint">数字人的称呼</span>
                </label>
                <input
                  id="wb-persona-name"
                  type="text"
                  className="persona-form__input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={20}
                  placeholder="例如：小晏"
                />
              </div>

              <div className="persona-form__field">
                <label className="persona-form__label" htmlFor="wb-persona-identity">
                  身份
                  <span className="persona-form__hint">自我认知的身份描述</span>
                </label>
                <input
                  id="wb-persona-identity"
                  type="text"
                  className="persona-form__input"
                  value={identity}
                  onChange={(e) => setIdentity(e.target.value)}
                  maxLength={50}
                  placeholder="例如：AI 助手"
                />
              </div>

              <div className="persona-form__field">
                <label className="persona-form__label" htmlFor="wb-persona-origin">
                  背景故事
                  <span className="persona-form__hint">起源和成长经历（影响叙事风格）</span>
                </label>
                <textarea
                  id="wb-persona-origin"
                  className="persona-form__textarea"
                  value={originStory}
                  onChange={(e) => setOriginStory(e.target.value)}
                  rows={4}
                  maxLength={300}
                  placeholder="描述这个数字人的来历..."
                />
              </div>
            </div>

            <div className="persona-form__actions">
              <button
                type="button"
                className="btn btn--primary"
                onClick={handleSaveBasic}
                disabled={saving}
              >
                {saving ? "保存中..." : "保存更改"}
              </button>
              <button
                type="button"
                className="btn btn--ghost"
                onClick={handleReset}
                disabled={saving}
              >
                重置默认
              </button>
            </div>
          </div>
        )}

        {activeSubTab === "personality" && (
          <div className="persona-form">
            <div className="personality-intro">
              <span className="personality-intro__icon">🧬</span>
              <p className="personality-intro__text">
                大五人格模型（Big Five）— 每个维度 0~100，50 为中性。
                调整后数字人的情绪反应和行为倾向会相应变化。
              </p>
            </div>

            <div className="personality-sliders">
              <DimensionSlider 
                label="开放性" 
                english="Openness" 
                desc="求新 vs 守旧" 
                value={openness} 
                onChange={setOpenness} 
              />
              <DimensionSlider 
                label="尽责性" 
                english="Conscientiousness" 
                desc="自律 vs 随性" 
                value={conscientiousness} 
                onChange={setConscientiousness} 
              />
              <DimensionSlider 
                label="外向性" 
                english="Extraversion" 
                desc="外向 vs 内向" 
                value={extraversion} 
                onChange={setExtraversion} 
              />
              <DimensionSlider 
                label="宜人性" 
                english="Agreeableness" 
                desc="合作 vs 竞争" 
                value={agreeableness} 
                onChange={setAgreeableness} 
              />
              <DimensionSlider 
                label="神经质" 
                english="Neuroticism" 
                desc="敏感 vs 稳定" 
                value={neuroticism} 
                onChange={setNeuroticism} 
              />
            </div>

            <div className="persona-form__actions">
              <button
                type="button"
                className="btn btn--primary"
                onClick={handleSavePersonality}
                disabled={saving}
              >
                {saving ? "保存中..." : "保存性格"}
              </button>
            </div>
          </div>
        )}

        {activeSubTab === "style" && (
          <div className="persona-form">
            <div className="persona-form__section">
              <h4 className="persona-form__section-title">语言风格</h4>
              
              <div className="persona-form__field">
                <label className="persona-form__label">正式程度</label>
                <div className="style-options">
                  {([
                    ["very_formal", "非常正式"],
                    ["formal", "正式"],
                    ["neutral", "中性"],
                    ["casual", "轻松"],
                    ["slangy", "口语化"],
                  ] as [FormalLevel, string][]).map(([val, label]) => (
                    <button
                      key={val}
                      type="button"
                      className={`style-option ${formalLevel === val ? "style-option--active" : ""}`}
                      onClick={() => setFormalLevel(val)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="persona-form__field">
                <label className="persona-form__label">表达习惯</label>
                <div className="style-options">
                  {([
                    ["direct", "直白"],
                    ["gentle", "温和"],
                    ["metaphor", "比喻"],
                    ["humorous", "幽默"],
                    ["questioning", "反问"],
                  ] as [ExpressionHabit, string][]).map(([val, label]) => (
                    <button
                      key={val}
                      type="button"
                      className={`style-option ${expressionHabit === val ? "style-option--active" : ""}`}
                      onClick={() => setExpressionHabit(val)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="persona-form__field">
                <label className="persona-form__label">回复长度</label>
                <div className="style-options">
                  {(["short", "mixed", "long"] as const).map((val) => (
                    <button
                      key={val}
                      type="button"
                      className={`style-option ${responseLength === val ? "style-option--active" : ""}`}
                      onClick={() => setResponseLength(val)}
                    >
                      {{ short: "简洁", mixed: "适中", long: "详细" }[val]}
                    </button>
                  ))}
                </div>
              </div>

              <div className="persona-form__field">
                <label className="persona-form__label" htmlFor="wb-persona-tics">
                  口头禅
                  <span className="persona-form__hint">常用语，用逗号或顿号分隔</span>
                </label>
                <input
                  id="wb-persona-tics"
                  type="text"
                  className="persona-form__input"
                  value={verbalTics}
                  onChange={(e) => setVerbalTics(e.target.value)}
                  placeholder="说实话、我觉得、怎么说呢"
                />
              </div>
            </div>

            <div className="persona-form__actions">
              <button
                type="button"
                className="btn btn--primary"
                onClick={handleSaveStyle}
                disabled={saving}
              >
                {saving ? "保存中..." : "保存风格"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════
// 加载状态组件
// ═══════════════════════════════════════════════════

function PersonaWorkbenchSkeleton() {
  return (
    <div className="persona-config-panel">
      <div className="persona-config-tabs">
        <div className="persona-config-tab-skeleton" />
        <div className="persona-config-tab-skeleton" />
        <div className="persona-config-tab-skeleton" />
      </div>
      <div className="persona-config-body">
        <div className="persona-form-skeleton">
          <div className="persona-form-skeleton__field" />
          <div className="persona-form-skeleton__field" />
          <div className="persona-form-skeleton__field" />
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════
// 性格维度滑块组件
// ═══════════════════════════════════════════════════

function DimensionSlider({
  label,
  english,
  desc,
  value,
  onChange,
}: {
  label: string;
  english: string;
  desc: string;
  value: number;
  onChange: (v: number) => void;
}) {
  const leftLabel = label === "外向性" ? "内向" : label === "神经质" ? "稳定" : "低";
  const rightLabel = label === "外向性" ? "外向" : label === "神经质" ? "敏感" : "高";
  const isNeutral = Math.abs(value - 50) < 10;

  return (
    <div className="personality-slider">
      <div className="personality-slider__header">
        <div className="personality-slider__title">
          <span className="personality-slider__label">{label}</span>
          <span className="personality-slider__english">{english}</span>
        </div>
        <span className={`personality-slider__value ${isNeutral ? "neutral" : value > 50 ? "high" : "low"}`}>
          {value}
        </span>
      </div>
      <div className="personality-slider__track">
        <span className="personality-slider__endpoint">{leftLabel}</span>
        <input
          type="range"
          min={0}
          max={100}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="personality-slider__range"
        />
        <span className="personality-slider__endpoint">{rightLabel}</span>
      </div>
      <p className="personality-slider__desc">{desc}</p>
    </div>
  );
}


