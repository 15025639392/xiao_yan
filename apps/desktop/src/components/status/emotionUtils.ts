export function getEmotionIcon(emotion: string): string {
  const icons: Record<string, string> = {
    joy: "😊",
    sadness: "😢",
    anger: "😠",
    fear: "😨",
    surprise: "😲",
    disgust: "🤢",
    calm: "😌",
    engaged: "🎯",
    proud: "😤",
    lonely: "😔",
    grateful: "🙏",
    frustrated: "😤",
  };
  return icons[emotion] || "😐";
}

export function getEmotionLabel(emotion: string): string {
  const labels: Record<string, string> = {
    joy: "喜悦",
    sadness: "悲伤",
    anger: "愤怒",
    fear: "恐惧",
    surprise: "惊讶",
    disgust: "厌恶",
    calm: "平静",
    engaged: "专注",
    proud: "自豪",
    lonely: "孤独",
    grateful: "感激",
    frustrated: "挫折",
  };
  return labels[emotion] || emotion;
}

export function getIntensityLabel(intensity: string): string {
  const labels: Record<string, string> = {
    none: "无",
    mild: "轻微",
    moderate: "中等",
    strong: "强烈",
    intense: "强烈",
  };
  return labels[intensity] || intensity;
}

export function getEmotionBgColor(emotion: string): string {
  const colors: Record<string, string> = {
    joy: "var(--success-muted)",
    sadness: "var(--info-muted)",
    anger: "var(--danger-muted)",
    fear: "var(--warning-muted)",
    surprise: "var(--info-muted)",
    disgust: "var(--warning-muted)",
    calm: "var(--success-muted)",
    engaged: "var(--info-muted)",
    proud: "var(--success-muted)",
    lonely: "var(--info-muted)",
    grateful: "var(--success-muted)",
    frustrated: "var(--danger-muted)",
  };
  return colors[emotion] || "var(--bg-surface-elevated)";
}

export function getEmotionBorderColor(emotion: string): string {
  const colors: Record<string, string> = {
    joy: "var(--success)",
    sadness: "var(--info)",
    anger: "var(--danger)",
    fear: "var(--warning)",
    surprise: "var(--info)",
    disgust: "var(--warning)",
    calm: "var(--success)",
    engaged: "var(--info)",
    proud: "var(--success)",
    lonely: "var(--info)",
    grateful: "var(--success)",
    frustrated: "var(--danger)",
  };
  return colors[emotion] || "var(--border-default)";
}

export function getMoodValenceLabel(moodValence: number): string {
  if (moodValence > 0) return "积极";
  if (moodValence < 0) return "消极";
  return "中立";
}

export function getArousalLabel(arousal: number): string {
  return arousal > 0.5 ? "高" : "低";
}
