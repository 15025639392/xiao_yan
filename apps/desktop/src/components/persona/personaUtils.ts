export function getEmotionDisplay(
  emotion: string,
  intensity: string,
): {
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

  const base = map[emotion] || { emoji: "😐", label: emotion, color: "#9ca3af" };
  if (intensity === "strong" || intensity === "intense") {
    return { ...base, label: `很${base.label}` };
  }
  return base;
}

export function moodBarColor(moodPercent: number): string {
  if (moodPercent > 60) return "var(--success)";
  if (moodPercent > 40) return "var(--warning)";
  return "var(--danger)";
}

export function parseVerbalTics(value: string): string[] | undefined {
  const parsed = value
    .split(/[,，、]/)
    .map((s) => s.trim())
    .filter(Boolean);
  return parsed.length > 0 ? parsed : undefined;
}

