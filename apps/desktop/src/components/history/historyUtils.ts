import { formatDurationBetween, formatRelativeTimeZh } from "../../lib/utils";

export function formatRelativeTime(iso: string): string {
  return formatRelativeTimeZh(iso, { spacing: "spaced" });
}

export function formatDuration(start: string, end: string): string {
  return formatDurationBetween(start, end);
}
