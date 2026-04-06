type RelativeTimeSpacing = "compact" | "spaced";
type RelativeDateFallback = "none" | "short" | "full";

type FormatRelativeTimeZhOptions = {
  spacing?: RelativeTimeSpacing;
  maxRelativeDays?: number;
  dateFallback?: RelativeDateFallback;
};

function parseDate(dateLike: string | Date | null | undefined): Date | null {
  if (!dateLike) {
    return null;
  }
  const date = dateLike instanceof Date ? dateLike : new Date(dateLike);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date;
}

export function formatRelativeTimeZh(
  dateLike: string | Date | null | undefined,
  options: FormatRelativeTimeZhOptions = {},
): string {
  const date = parseDate(dateLike);
  if (!date) {
    return "";
  }

  const spacing = options.spacing ?? "compact";
  const maxRelativeDays = options.maxRelativeDays ?? Number.POSITIVE_INFINITY;
  const dateFallback = options.dateFallback ?? "none";

  const diffMs = Math.max(Date.now() - date.getTime(), 0);
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return spacing === "spaced" ? `${diffMin} 分钟前` : `${diffMin}分钟前`;

  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return spacing === "spaced" ? `${diffHr} 小时前` : `${diffHr}小时前`;

  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < maxRelativeDays) {
    return spacing === "spaced" ? `${diffDay} 天前` : `${diffDay}天前`;
  }

  if (dateFallback === "short") {
    return date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
  }
  if (dateFallback === "full") {
    return date.toLocaleDateString("zh-CN");
  }

  return spacing === "spaced" ? `${diffDay} 天前` : `${diffDay}天前`;
}

export function formatDurationBetween(startLike: string | Date, endLike: string | Date): string {
  const start = parseDate(startLike);
  const end = parseDate(endLike);
  if (!start || !end) {
    return "0s";
  }

  const ms = Math.max(end.getTime() - start.getTime(), 0);
  const secs = Math.floor(ms / 1000);
  if (secs < 60) {
    return `${secs}s`;
  }

  const mins = Math.floor(secs / 60);
  return `${mins}m ${secs % 60}s`;
}
