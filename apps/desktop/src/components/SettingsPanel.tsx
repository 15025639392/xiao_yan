import { useState, useEffect } from "react";
import type {
  PersonaProfile,
  FormalLevel,
  ExpressionHabit,
} from "../lib/api";
import {
  fetchPersona,
  updatePersona,
  updatePersonality,
  updateSpeakingStyle,
  resetPersona,
} from "../lib/api";
import { MemoryPanel } from "./MemoryPanel";
import { PersonaCard } from "./PersonaCard";

type SettingsPanelProps = {
  theme: "dark" | "light";
  onThemeChange: (theme: "dark" | "light") => void;
  onPersonaUpdated?: () => void;
};

// ═══════════════════════════════════════════════════
// 人格工作台 - 完整的人格管理中心
// ═══════════════════════════════════════════════════

export function SettingsPanel({ theme, onThemeChange, onPersonaUpdated }: SettingsPanelProps) {
  const [activeTab, setActiveTab] = useState<"persona" | "memory" | "appearance" | "system">("persona");

  return (
    <section className="workbench-page">
      {/* 页面头部 */}
      <header className="workbench-page__header">
        <div className="workbench-page__title-group">
          <h2 className="workbench-page__title">人格工作台</h2>
          <p className="workbench-page__subtitle">管理数字人的人格、记忆与系统设置</p>
        </div>
        <div className="workbench-page__version">v0.1.0</div>
      </header>

      {/* 工作台主体 - 左右分栏 */}
      <div className="workbench-layout">
        {/* 左侧：导航 + 实时状态 */}
        <aside className="workbench-sidebar">
          {/* 导航菜单 */}
          <nav className="workbench-nav">
            <button
              type="button"
              className={`workbench-nav__item ${activeTab === "persona" ? "workbench-nav__item--active" : ""}`}
              onClick={() => setActiveTab("persona")}
            >
              <span className="workbench-nav__icon">🎭</span>
              <span className="workbench-nav__label">人格配置</span>
              <span className="workbench-nav__desc">性格、风格、身份设置</span>
            </button>
            <button
              type="button"
              className={`workbench-nav__item ${activeTab === "memory" ? "workbench-nav__item--active" : ""}`}
              onClick={() => setActiveTab("memory")}
            >
              <span className="workbench-nav__icon">🧠</span>
              <span className="workbench-nav__label">记忆库</span>
              <span className="workbench-nav__desc">查看与管理记忆</span>
            </button>
            <button
              type="button"
              className={`workbench-nav__item ${activeTab === "appearance" ? "workbench-nav__item--active" : ""}`}
              onClick={() => setActiveTab("appearance")}
            >
              <span className="workbench-nav__icon">🎨</span>
              <span className="workbench-nav__label">外观</span>
              <span className="workbench-nav__desc">主题与界面设置</span>
            </button>
            <button
              type="button"
              className={`workbench-nav__item ${activeTab === "system" ? "workbench-nav__item--active" : ""}`}
              onClick={() => setActiveTab("system")}
            >
              <span className="workbench-nav__icon">⚙️</span>
              <span className="workbench-nav__label">系统</span>
              <span className="workbench-nav__desc">关于与高级选项</span>
            </button>
          </nav>

          {/* 实时人格状态卡片 */}
          <div className="workbench-sidebar__section">
            <h4 className="workbench-sidebar__section-title">当前状态</h4>
            <PersonaCard />
          </div>
        </aside>

        {/* 右侧：内容区域 */}
        <main className="workbench-content">
          {activeTab === "persona" ? (
            <PersonaWorkbench onUpdated={onPersonaUpdated} />
          ) : activeTab === "memory" ? (
            <MemoryWorkbench />
          ) : activeTab === "appearance" ? (
            <AppearanceWorkbench theme={theme} onThemeChange={onThemeChange} />
          ) : (
            <SystemWorkbench />
          )}
        </main>
      </div>
    </section>
  );
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
    return (
      <div className="workbench-panel workbench-panel--loading">
        <div className="workbench-panel__skeleton">
          <div className="workbench-skeleton-header" />
          <div className="workbench-skeleton-body" />
        </div>
      </div>
    );
  }

  const subTabs = [
    { id: "basic" as const, label: "基础信息", icon: "👤" },
    { id: "personality" as const, label: "性格维度", icon: "🧬" },
    { id: "style" as const, label: "说话风格", icon: "💬" },
  ];

  return (
    <div className="workbench-panel">
      {/* 面板头部 */}
      <header className="workbench-panel__header">
        <h3 className="workbench-panel__title">人格配置</h3>
        {toast && <span className="workbench-panel__toast">{toast}</span>}
      </header>

      {/* 子标签切换 */}
      <div className="workbench-subtabs">
        {subTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`workbench-subtab ${activeSubTab === tab.id ? "workbench-subtab--active" : ""}`}
            onClick={() => setActiveSubTab(tab.id)}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* 内容区域 */}
      <div className="workbench-panel__body">
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

// ═══════════════════════════════════════════════════
// 记忆库工作台
// ═══════════════════════════════════════════════════

function MemoryWorkbench() {
  return (
    <div className="workbench-panel workbench-panel--full">
      <header className="workbench-panel__header">
        <h3 className="workbench-panel__title">记忆库</h3>
        <p className="workbench-panel__subtitle">浏览、搜索和管理数字人的记忆</p>
      </header>
      <div className="workbench-panel__body workbench-panel__body--padded">
        <MemoryPanel />
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════
// 外观设置工作台
// ═══════════════════════════════════════════════════

function AppearanceWorkbench({ 
  theme, 
  onThemeChange 
}: { 
  theme: "dark" | "light"; 
  onThemeChange: (theme: "dark" | "light") => void;
}) {
  return (
    <div className="workbench-panel">
      <header className="workbench-panel__header">
        <h3 className="workbench-panel__title">外观设置</h3>
      </header>
      <div className="workbench-panel__body">
        <div className="appearance-section">
          <h4 className="appearance-section__title">
            <PaletteIcon /> 主题
          </h4>
          <p className="appearance-section__desc">选择界面的颜色主题</p>
          
          <div className="theme-cards">
            <button
              type="button"
              className={`theme-card ${theme === "dark" ? "theme-card--active" : ""}`}
              onClick={() => onThemeChange("dark")}
            >
              <div className="theme-card__preview theme-card__preview--dark">
                <div className="theme-card__preview-bar" />
                <div className="theme-card__preview-content">
                  <div className="theme-card__preview-line" />
                  <div className="theme-card__preview-line theme-card__preview-line--short" />
                </div>
              </div>
              <div className="theme-card__info">
                <MoonIcon />
                <span>深色</span>
              </div>
            </button>

            <button
              type="button"
              className={`theme-card ${theme === "light" ? "theme-card--active" : ""}`}
              onClick={() => onThemeChange("light")}
            >
              <div className="theme-card__preview theme-card__preview--light">
                <div className="theme-card__preview-bar" />
                <div className="theme-card__preview-content">
                  <div className="theme-card__preview-line" />
                  <div className="theme-card__preview-line theme-card__preview-line--short" />
                </div>
              </div>
              <div className="theme-card__info">
                <SunIcon />
                <span>浅色</span>
              </div>
            </button>
          </div>
        </div>

        <div className="appearance-section appearance-section--placeholder">
          <h4 className="appearance-section__title">
            <BellIcon /> 通知
          </h4>
          <p className="appearance-section__desc">通知设置即将推出</p>
        </div>

        <div className="appearance-section appearance-section--placeholder">
          <h4 className="appearance-section__title">
            <KeyboardIcon /> 快捷键
          </h4>
          <p className="appearance-section__desc">快捷键设置即将推出</p>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════
// 系统设置工作台
// ═══════════════════════════════════════════════════

function SystemWorkbench() {
  return (
    <div className="workbench-panel">
      <header className="workbench-panel__header">
        <h3 className="workbench-panel__title">系统信息</h3>
      </header>
      <div className="workbench-panel__body">
        <div className="system-info">
          <div className="system-info__item">
            <span className="system-info__label">版本</span>
            <span className="system-info__value">v0.1.0</span>
          </div>
          <div className="system-info__item">
            <span className="system-info__label">数字人控制台</span>
            <span className="system-info__value">AI Agent Desktop</span>
          </div>
          <div className="system-info__item">
            <span className="system-info__label">人格系统</span>
            <span className="system-info__value">Phase 9</span>
          </div>
          <div className="system-info__item">
            <span className="system-info__label">记忆系统</span>
            <span className="system-info__value">Phase 8</span>
          </div>
        </div>

        <div className="appearance-section appearance-section--placeholder">
          <h4 className="appearance-section__title">
            <ShieldIcon /> 数据与隐私
          </h4>
          <p className="appearance-section__desc">数据与隐私设置即将推出</p>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════
// 图标组件
// ═══════════════════════════════════════════════════

function PaletteIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 8v8" />
      <path d="M8 12h8" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function KeyboardIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="2" y="4" width="20" height="16" rx="2" ry="2" />
      <line x1="6" y1="8" x2="6" y2="8" />
      <line x1="10" y1="8" x2="10" y2="8" />
      <line x1="14" y1="8" x2="14" y2="8" />
      <line x1="18" y1="8" x2="18" y2="8" />
      <line x1="6" y1="12" x2="6" y2="12" />
      <line x1="10" y1="12" x2="10" y2="12" />
      <line x1="14" y1="12" x2="14" y2="12" />
      <line x1="18" y1="12" x2="18" y2="12" />
      <line x1="6" y1="16" x2="18" y2="16" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
