import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import type { BeingState, PersonaProfile } from "../../lib/api";
import { AvatarStage } from "./AvatarStage";

const state: BeingState = {
  mode: "awake",
  focus_mode: "autonomy",
  current_thought: null,
  active_goal_ids: [],
};

const persona = {
  name: "小晏",
  identity: "持续存在的数字人",
  emotion: {
    primary_emotion: "calm",
    primary_intensity: "none",
    secondary_emotion: null,
    secondary_intensity: "none",
    mood_valence: 0,
    arousal: 0.3,
    is_calm: true,
    active_entry_count: 0,
    active_entries: [],
    last_updated: null,
  },
  personality: {
    openness: 72,
    conscientiousness: 60,
    extraversion: 40,
    agreeableness: 68,
    neuroticism: 45,
  },
} as PersonaProfile;

test("renders the standalone avatar stage without panel chrome", () => {
  render(<AvatarStage state={state} persona={persona} />);

  expect(screen.getByLabelText("VRM 外显状态")).toHaveClass("avatar-stage");
  expect(screen.queryByText("VRM 外显层")).not.toBeInTheDocument();
  expect(screen.queryByText("VRM 外显未启用")).not.toBeInTheDocument();
});
