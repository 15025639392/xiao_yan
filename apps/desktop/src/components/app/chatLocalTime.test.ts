import { buildLocalChatTimeContext } from "./chatLocalTime";

test("builds local chat time context from the current device time", () => {
  const originalResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
  Intl.DateTimeFormat.prototype.resolvedOptions = () =>
    ({
      locale: "zh-CN",
      calendar: "gregory",
      numberingSystem: "latn",
      timeZone: "Asia/Shanghai",
    }) as Intl.ResolvedDateTimeFormatOptions;

  try {
    expect(buildLocalChatTimeContext(new Date(2026, 3, 18, 12, 30))).toEqual({
      user_timezone: "Asia/Shanghai",
      user_local_time: "2026-04-18 12:30",
      user_time_of_day: "afternoon",
    });
  } finally {
    Intl.DateTimeFormat.prototype.resolvedOptions = originalResolvedOptions;
  }
});
