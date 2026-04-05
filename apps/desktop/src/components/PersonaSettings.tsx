import { useState, useEffect } from "react";
import type {
  PersonaProfile,
  FormalLevel,
  ExpressionHabit,
  SentenceStyleType,
} from "../lib/api";
import {
  fetchPersona,
  updatePersona,
  updatePersonality,
  updateSpeakingStyle,
  resetPersona,
} from "../lib/api";

type PersonaSettingsProps = {
  onUpdated?: () => void;
};

export function PersonaSettings({ onUpdated }: PersonaSettingsProps) {
  const [profile, setProfile] = useState<PersonaProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<"basic" | "personality" | "style">("basic");
  const [toast, setToast] = useState<string | null>(null);

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
      // 填充编辑表单
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
      "性格维度已更新";
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
      <section className="settings-section">
        <h3 className="settings-section__title">
          <span>🎭</span> 人格内核
        </h3>
        <div style={{ padding: "var(--space-6)", textAlign: "center", color: "var(--text-tertiary)" }}>
          加载中...
        </div>
      </section>
    );
  }

  const tabs = [
    { id: "basic" as const, label: "基础信息" },
    { id: "personality" as const, label: "性格" },
    { id: "style" as const, label: "说话风格" },
  ];

  return (
    <section className="settings-section settings-section--persona">
      <h3 className="settings-section__title">
        <span>🎭</span> 人格内核
        <span className="settings-section__badge">Phase 7</span>
      </h3>

      {/* Toast 提示 */}
      {toast ? (
        <div className="persona-settings__toast">{toast}</div>
      ) : null}

      {/* Tab 切换 */}
      <div className="persona-settings__tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`persona-settings__tab ${activeTab === tab.id ? "persona-settings__tab--active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── 基础信息 Tab ── */}
      {activeTab === "basic" ? (
        <div className="settings-section__body persona-settings__body">
          <div className="setting-item">
            <div className="setting-item__info">
              <label className="setting-item__label" htmlFor="persona-name">名字</label>
              <p className="setting-item__desc">数字人的称呼</p>
            </div>
            <input
              id="persona-name"
              type="text"
              className="setting-item__control-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={20}
            />
          </div>

          <div className="setting-item">
            <div className="setting-item__info">
              <label className="setting-item__label" htmlFor="persona-identity">身份</label>
              <p className="setting-item__desc">自我认知的身份描述</p>
            </div>
            <input
              id="persona-identity"
              type="text"
              className="setting-item__control-input"
              value={identity}
              onChange={(e) => setIdentity(e.target.value)}
              maxLength={50}
            />
          </div>

          <div className="setting-item">
            <div className="setting-item__info">
              <label className="setting-item__label" htmlFor="persona-origin">背景故事</label>
              <p className="setting-item__desc">起源和成长经历（影响叙事风格）</p>
            </div>
            <textarea
              id="persona-origin"
              className="setting-item__control-textarea"
              value={originStory}
              onChange={(e) => setOriginStory(e.target.value)}
              rows={3}
              maxLength={300}
            />
          </div>

          <div className="persona-settings__actions">
            <button
              type="button"
              className="btn btn--primary btn--sm"
              onClick={handleSaveBasic}
              disabled={saving}
            >
              {saving ? "保存中..." : "保存"}
            </button>
            <button
              type="button"
              className="btn btn--sm"
              onClick={handleReset}
              disabled={saving}
              style={{ color: "var(--danger)" }}
            >
              重置默认
            </button>
          </div>
        </div>
      ) : null}

      {/* ── 性格 Tab ── */}
      {activeTab === "personality" ? (
        <div className="settings-section__body persona-settings__body">
          <p className="persona-settings__hint">
            大五模型（Big Five）— 每个维度 0~100，50 为中性。调整后数字人的情绪反应和行为倾向会相应变化。
          </p>

          <DimensionSlider label="开放性 (Openness)" desc="求新 vs 守旧" value={openness} onChange={setOpenness} />
          <DimensionSlider label="尽责性 (Conscientiousness)" desc="自律 vs 随性" value={conscientiousness} onChange={setConscientiousness} />
          <DimensionSlider label="外向性 (Extraversion)" desc="外向 vs 内向" value={extraversion} onChange={setExtraversion} />
          <DimensionSlider label="宜人性 (Agreeableness)" desc="合作 vs 竞争" value={agreeableness} onChange={setAgreeableness} />
          <DimensionSlider label="神经质 (Neuroticism)" desc="敏感 vs 稳定" value={neuroticism} onChange={setNeuroticism} />

          <div className="persona-settings__actions">
            <button
              type="button"
              className="btn btn--primary btn--sm"
              onClick={handleSavePersonality}
              disabled={saving}
            >
              {saving ? "保存中..." : "保存性格"}
            </button>
          </div>
        </div>
      ) : null}

      {/* ── 说话风格 Tab ── */}
      {activeTab === "style" ? (
        <div className="settings-section__body persona-settings__body">
          <div className="setting-item">
            <div className="setting-item__info">
              <label className="setting-item__label">正式程度</label>
            </div>
            <div className="style-selector">
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

          <div className="setting-item">
            <div className="setting-item__info">
              <label className="setting-item__label">表达习惯</label>
            </div>
            <div className="style-selector">
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

          <div className="setting-item">
            <div className="setting-item__info">
              <label className="setting-item__label" htmlFor="persona-length">回复长度</label>
            </div>
            <div className="style-selector">
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

          <div className="setting-item">
            <div className="setting-item__info">
              <label className="setting-item__label" htmlFor="persona-tics">口头禅</label>
              <p className="setting-item__desc">常用语，用逗号或顿号分隔</p>
            </div>
            <input
              id="persona-tics"
              type="text"
              className="setting-item__control-input"
              value={verbalTics}
              onChange={(e) => setVerbalTics(e.target.value)}
              placeholder="说实话、我觉得、怎么说呢"
            />
          </div>

          <div className="persona-settings__actions">
            <button
              type="button"
              className="btn btn--primary btn--sm"
              onClick={handleSaveStyle}
              disabled={saving}
            >
              {saving ? "保存中..." : "保存风格"}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

// ── 子组件：性格维度滑块 ───────────────────────────────

function DimensionSlider({
  label,
  desc,
  value,
  onChange,
}: {
  label: string;
  desc: string;
  value: number;
  onChange: (v: number) => void;
}) {
  const leftLabel = label.includes("外向") ? "内向" : label.includes("神经") ? "稳定" : "低";
  const rightLabel = label.includes("外向") ? "外向" : label.includes("神经") ? "敏感" : "高";
  const isNeutral = Math.abs(value - 50) < 10;

  return (
    <div className="dim-slider">
      <div className="dim-slider__header">
        <span className="dim-slider__label">{label}</span>
        <span className="dim-slider__value">{value}</span>
      </div>
      <div className="dim-slider__track">
        <span className="dim-slider__min">{leftLabel}</span>
        <input
          type="range"
          min={0}
          max={100}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className={`dim-slider__range ${isNeutral ? "dim-slider__range--neutral" : value > 50 ? "dim-slider__range--high" : "dim-slider__range--low"}`}
        />
        <span className="dim-slider__max">{rightLabel}</span>
      </div>
      <p className="dim-slider__desc">{desc}</p>
    </div>
  );
}
