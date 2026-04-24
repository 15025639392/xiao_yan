import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

const { fetchState, fetchPersona } = vi.hoisted(() => ({
  fetchState: vi.fn(),
  fetchPersona: vi.fn(),
}));

const { subscribeAppRealtime } = vi.hoisted(() => ({
  subscribeAppRealtime: vi.fn(),
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    fetchState,
    fetchPersona,
  };
});

vi.mock("../../lib/realtime", () => ({
  subscribeAppRealtime,
}));

import { AvatarWindow } from "./AvatarWindow";

const runtimeState = {
  mode: "awake",
  focus_mode: "autonomy",
  current_thought: null,
  active_goal_ids: [],
};

const persona = {
  name: "小晏",
  identity: "持续存在的数字人",
  features: { avatar_enabled: true },
  emotion: {
    primary_emotion: "joy",
    primary_intensity: "moderate",
    secondary_emotion: null,
    secondary_intensity: "none",
    mood_valence: 0.5,
    arousal: 0.6,
    is_calm: false,
    active_entry_count: 1,
    active_entries: [],
    last_updated: null,
  },
};

test("loads initial state into the standalone avatar window", async () => {
  fetchState.mockResolvedValue(runtimeState);
  fetchPersona.mockResolvedValue(persona);
  subscribeAppRealtime.mockReturnValue(vi.fn());

  render(<AvatarWindow />);

  await waitFor(() => expect(fetchState).toHaveBeenCalled());
  expect(fetchPersona).toHaveBeenCalled();
  expect(subscribeAppRealtime).toHaveBeenCalled();
  expect(screen.getByLabelText("VRM 外显状态")).toHaveClass("avatar-stage");
});

beforeEach(() => {
  fetchState.mockReset();
  fetchPersona.mockReset();
  subscribeAppRealtime.mockReset();
});
