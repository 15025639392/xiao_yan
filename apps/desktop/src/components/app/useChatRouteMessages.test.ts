import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { fetchMessages } = vi.hoisted(() => ({
  fetchMessages: vi.fn(),
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    fetchMessages,
  };
});

import { useChatRouteMessages } from "./useChatRouteMessages";

describe("useChatRouteMessages", () => {
  beforeEach(() => {
    fetchMessages.mockReset();
  });

  it("fetches and merges messages when route becomes chat", async () => {
    fetchMessages.mockResolvedValue({
      messages: [
        { id: "user-1", role: "user", content: "你好" },
        { id: "assistant-1", role: "assistant", content: "我在。" },
      ],
    });

    const setMessages = vi.fn();

    renderHook(() =>
      useChatRouteMessages({
        route: "chat",
        setMessages,
      }),
    );

    await waitFor(() => {
      expect(fetchMessages).toHaveBeenCalled();
      expect(setMessages).toHaveBeenCalled();
    });
  });

  it("does nothing when current route is not chat", () => {
    const setMessages = vi.fn();

    renderHook(() =>
      useChatRouteMessages({
        route: "persona",
        setMessages,
      }),
    );

    expect(fetchMessages).not.toHaveBeenCalled();
    expect(setMessages).not.toHaveBeenCalled();
  });
});
