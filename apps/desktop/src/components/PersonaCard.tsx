import { useState, useEffect } from "react";
import type { PersonaSummary, EmotionType, EmotionState, StyleOverrideConfig, ExpressionStyleResponse } from "../lib/api";
import { fetchPersonaSummary, fetchEmotionState, fetchExpressionStyle } from "../lib/api";

type PersonaCardProps = {
  className?: string;
};

/** 情绪类型 → 中文显示名 + emoji */
const EMOTION_LABELS: Record<EmotionType, { label: string; emoji: string; color: string }> = {
  joy: { label: "开心", emoji: "😊", color: "var(--success)" },
  sadness: { label: "失落", emoji: "😢", color: "var(--info)" },
  anger: { label: "烦躁", emoji: "😤", color: "var(--danger)" },
  fear: { label: "担忧", emoji: "😰", color: "var(--warning)" },
  surprise: { label: "惊讶", emoji: "😲", color: "var(--primary)" },
  disgust: { label: "不适", emoji: "🫠", color: "var(--text-tertiary)" },
  calm: { label: "平静", emoji: "😌", color: "var(--success)" },
  engaged: { label: "投入", emoji: "🎯", color: "var(--primary)" },
  proud: { label: "自豪", emoji: "🏆", color: "var(--success)" },
  lonely: { label: "孤独", emoji: "🥀", color: "var(--text-secondary)" },
  grateful: { label: "感激", emoji: "🙏", color: "var(--success)" },
  frustrated: { label: "挫败", emoji: "😩", color: "var(--warning)" },
};

const INTENSITY_LABELS: Record<string, string> = {
  none: "",
  mild: "轻微",
  moderate: "中等",
  strong: "强烈",
  intense: "极强",
};

/** 性格维度中文标签 */
const PERSONALITY_LABELS: Record<string, string> = {
  openness: "开放性",
  conscientiousness: "尽责性",
  extraversion: "外向性",
  agreeableness: "宜人性",
  neuroticism: "神经质",
};

// ── Phase 9: 表达风格维度标签 ──

const VOLUME_LABELS: Record<string, { label: string; icon: string }> = {
  very_brief: { label: "极简", icon: "··" },
  brief: { label: "简洁", icon: "·" },
  normal: { label: "正常", icon: "—•—" },
  verbose: { label: "偏多", icon: "——" },
  very_verbose: { label: "滔滔不绝", icon: "———" },
};

const EMOJI_LABELS: Record<string, { label: string; icon: string }> = {
  never: { label: "不用", icon: "🚫" },
  rarely: { label: "偶尔", icon: "🫣" },
  sometimes: { label: "有时", icon: "🙂" },
  often: { label: "经常", icon: "😄" },
  frequently: { label: "丰富", icon: "🎉" },
};

const PATTERN_LABELS: Record<string, { label: string; icon: string }> = {
  fragmented: { label: "碎片化", icon: "▪️" },
  short_direct: { label: "干脆利落", icon: "⚡" },
  balanced: { label: "平衡", icon: "⚖️" },
  exclamatory: { label: "感叹多", icon: "❗" },
  elaborate: { label: "展开说", icon: "📝" },
};

const TONE_LABELS: Record<string, { label: string; icon: string }> = {
  flat: { label: "平淡", icon: "— " },
  gentle: { label: "温和", icon: "🌸" },
  playful: { label: "活泼", icon: "✨" },
  intense: { label: "强烈", icon: "🔥" },
  hesitant: { label: "犹豫", icon: "💭" },
  sarcastic: { label: "讽刺", icon: "🙃" },
};

export function PersonaCard({ className }: PersonaCardProps) {
  const [summary, setSummary] = useState<PersonaSummary | null>(null);
  const [emotion, setEmotion] = useState<EmotionState | null>(null);
  const [expressionStyle, setExpressionStyle] = useState<ExpressionStyleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPersona();
    // 每 30 秒刷新一次情绪和风格状态
    const id = setInterval(loadEmotionAndStyle, 30000);
    return () => clearInterval(id);
  }, []);

  async function loadPersona() {
    try {
      setLoading(true);
      const [summaryData, emotionData, styleData] = await Promise.all([
        fetchPersonaSummary(),
        fetchEmotionState(),
        fetchExpressionStyle().catch(() => null), // 新接口，失败不阻塞
      ]);
      setSummary(summaryData);
      setEmotion(emotionData);
      setExpressionStyle(styleData);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadEmotionAndStyle() {
    try {
      const [emotionData, styleData] = await Promise.all([
        fetchEmotionState(),
        fetchExpressionStyle().catch(() => null),
      ]);
      setEmotion(emotionData);
      if (styleData) setExpressionStyle(styleData);
    } catch {
      // 静默失败
    }
  }

  if (loading && !summary) {
    return (
      <section className={`persona-card persona-card--loading ${className ?? ""}`}>
        <div className="persona-card__skeleton">
          <div className="persona-card__avatar-skeleton" />
          <div className="persona-card__info-skeleton" />
        </div>
      </section>
    );
  }

  if (error || !summary) {
    return (
      <section className={`persona-card ${className ?? ""}`}>
        <p style={{ color: "var(--text-tertiary)", fontSize: "0.8rem" }}>
          人格信息加载失败
        </p>
      </section>
    );
  }

  const primary = emotion?.primary_emotion ?? "calm";
  const primaryInfo = EMOTION_LABELS[primary] ?? EMOTION_LABELS.calm;
  const secondary = emotion?.secondary_emotion;
  const secondaryInfo = secondary ? EMOTION_LABELS[secondary] : null;

  // 心情条：mood_valence -1 ~ 1 映射到宽度
  const moodPercent = ((emotion?.mood_valence ?? 0) + 1) * 50; // 0~100
  const moodColor =
    (emotion?.mood_valence ?? 0) > 0.2
      ? "var(--success)"
      : (emotion?.mood_valence ?? 0) < -0.2
        ? "var(--danger)"
        : "var(--text-tertiary)";

  // 表达风格数据（Phase 9）
  const styleOverride = expressionStyle?.style_override;
  const hasActiveStyle = expressionStyle?.has_active_style ?? false;

  return (
    <section className={`persona-card ${className ?? ""}`}>
      {/* 头部：名字 + 情绪状态 */}
      <div className="persona-card__header">
        <div className="persona-card__identity">
          <span className="persona-card__name">{summary.name}</span>
          <span className="persona-card__version">v{summary.version}</span>
        </div>
        <div
          className="persona-card__emotion-badge"
          style={{ borderColor: primaryInfo.color }}
          title={`${primaryInfo.label}${emotion?.primary_intensity !== "none" ? `（${INTENSITY_LABELS[emotion.primary_intensity ?? "none"] ?? ""}）` : ""}`}
        >
          <span>{primaryInfo.emoji}</span>
          <span>{primaryInfo.label}</span>
        </div>
      </div>

      {/* 心情条 */}
      <div className="persona-card__mood-bar">
        <div className="persona-card__mood-track">
          <div
            className="persona-card__mood-fill"
            style={{
              width: `${moodPercent}%`,
              backgroundColor: moodColor,
            }}
          />
        </div>
        <span className="persona-card__mood-label">
          {(emotion?.mood_valence ?? 0).toFixed(2)}
        </span>
      </div>

      {/* 性格标签 */}
      {summary.personality_traits.length > 0 ? (
        <div className="persona-card__traits">
          {summary.personality_traits.slice(0, 4).map((trait) => (
            <span key={trait} className="persona-card__trait-tag">
              {trait}
            </span>
          ))}
        </div>
      ) : null}

      {/* 次要情绪 */}
      {secondaryInfo && emotion && emotion.secondary_intensity !== "none" ? (
        <div className="persona-card__secondary-emotion">
          <span>{secondaryInfo.emoji}</span>
          <span>同时{INTENSITY_LABELS[emotion.secondary_intensity]}{secondaryInfo.label}</span>
        </div>
      ) : null}

      {/* ══ Phase 9: 表达风格指示器 ══ */}
      {hasActiveStyle && styleOverride && expressionStyle ? (
        <div className="persona-card__expression-style">
          <div className="persona-card__expression-header">
            <span className="persona-card__expression-icon">
              🎭
            </span>
            <span className="persona-card__expression-title">
              当前表达风格
            </span>
            <span
              className="persona-card__expression-badge"
              style={{ borderColor: primaryInfo.color }}
            >
              受{primaryInfo.label}影响
            </span>
          </div>

          {/* 风格维度条 */}
          <div className="persona-card__style-dimensions">
            {/* 话量 */}
            <div className="persona-card__style-dim" title={`回复话量：${VOLUME_LABELS[styleOverride.volume]?.label ?? styleOverride.volume}`}>
              <span className="persona-card__dim-icon">{VOLUME_LABELS[styleOverride.volume]?.icon ?? "—"}</span>
              <span className="persona-card__dim-label">话量</span>
              <span className="persona-card__dim-value">{VOLUME_LABELS[styleOverride.volume]?.label ?? styleOverride.volume}</span>
            </div>

            {/* Emoji */}
            <div className="persona-card__style-dim" title={`Emoji 使用：${EMOJI_LABELS[styleOverride.emoji_level]?.label ?? styleOverride.emoji_level}`}>
              <span className="persona-card__dim-icon">{EMOJI_LABELS[styleOverride.emoji_level]?.icon ?? "?"}</span>
              <span className="persona-card__dim-label">表情</span>
              <span className="persona-card__dim-value">{EMOJI_LABELS[styleOverride.emoji_level]?.label ?? styleOverride.emoji_level}</span>
            </div>

            {/* 句式 */}
            <div className="persona-card__style-dim" title={`句式偏好：${PATTERN_LABELS[styleOverride.sentence_pattern]?.label ?? styleOverride.sentence_pattern}`}>
              <span className="persona-card__dim-icon">{PATTERN_LABELS[styleOverride.sentence_pattern]?.icon ?? "—"}</span>
              <span className="persona-card__dim-label">句式</span>
              <span className="persona-card__dim-value">{PATTERN_LABELS[styleOverride.sentence_pattern]?.label ?? styleOverride.sentence_pattern}</span>
            </div>

            {/* 语气 */}
            <div className="persona-card__style-dim" title={`语气：${TONE_LABELS[styleOverride.tone_modifier]?.label ?? styleOverride.tone_modifier}`}>
              <span className="persona-card__dim-icon">{TONE_LABELS[styleOverride.tone_modifier]?.icon ?? "—"}</span>
              <span className="persona-card__dim-label">语气</span>
              <span className="persona-card__dim-value">{TONE_LABELS[styleOverride.tone_modifier]?.label ?? styleOverride.tone_modifier}</span>
            </div>
          </div>

          {/* 风格指令预览 */}
          {expressionStyle.style_instruction ? (
            <div className="persona-card__style-instruction">
              <p>{expressionStyle.style_instruction.length > 80
                ? `${expressionStyle.style_instruction.slice(0, 80)}…`
                : expressionStyle.style_instruction}
              </p>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* 最近情绪事件 */}
      {emotion && emotion.active_entries.length > 0 ? (
        <div className="persona-card__recent-events">
          {emotion.active_entries.slice(-3).reverse().map((entry, idx) => {
            const info = EMOTION_LABELS[entry.emotion_type];
            return (
              <div key={idx} className="persona-card__event-item">
                <span>{info?.emoji ?? "•"}</span>
                <span className="persona-card__event-reason">
                  {entry.reason || info?.label || entry.emotion_type}
                </span>
                <span className="persona-card__event-source">{entry.source}</span>
              </div>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
