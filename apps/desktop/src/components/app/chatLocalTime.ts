import type { ChatRequestBody } from "../../lib/api";

export function buildLocalChatTimeContext(date = new Date()): Pick<
  ChatRequestBody,
  "user_timezone" | "user_local_time" | "user_time_of_day"
> {
  return {
    user_timezone: resolveUserTimezone(),
    user_local_time: formatLocalTimestamp(date),
    user_time_of_day: resolveTimeOfDay(date.getHours()),
  };
}

function resolveUserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "local";
}

function resolveTimeOfDay(hour: number): ChatRequestBody["user_time_of_day"] {
  if (hour < 6 || hour >= 22) {
    return "night";
  }
  if (hour < 12) {
    return "morning";
  }
  if (hour < 18) {
    return "afternoon";
  }
  return "evening";
}

function formatLocalTimestamp(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");

  return `${year}-${month}-${day} ${hours}:${minutes}`;
}
