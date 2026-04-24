import { expect, test } from "vitest";
import type { BeingState, EmotionState, PersonaProfile } from "../../lib/api";
import { mapAvatarState } from "./avatarStateMapper";

const baseState: BeingState = {
  mode: "awake",
  focus_mode: "autonomy",
  current_thought: null,
  active_goal_ids: [],
};

const baseEmotion: EmotionState = {
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
};

const basePersona = {
  personality: {
    extraversion: 40,
    neuroticism: 45,
  },
} as PersonaProfile;

test("maps sleeping state to sleep motion and closed eyes", () => {
  const result = mapAvatarState(
    { ...baseState, mode: "sleeping", focus_mode: "sleeping" },
    baseEmotion,
    basePersona,
  );

  expect(result.motion).toBe("sleeping");
  expect(result.expression).toBe("relaxed");
  expect(result.expressionWeight).toBeGreaterThan(0.6);
  expect(result.lookAt).toBe("down");
});

test("maps joy intensity to happy expression weight", () => {
  const result = mapAvatarState(
    baseState,
    { ...baseEmotion, primary_emotion: "joy", primary_intensity: "strong", arousal: 0.8 },
    basePersona,
  );

  expect(result.motion).toBe("idle");
  expect(result.expression).toBe("happy");
  expect(result.expressionWeight).toBe(0.85);
  expect(result.motionEnergy).toBeGreaterThan(0.7);
});

test("maps orchestrator focus to working motion", () => {
  const result = mapAvatarState(
    { ...baseState, focus_mode: "orchestrator", active_goal_ids: ["goal-1"] },
    { ...baseEmotion, primary_emotion: "engaged", primary_intensity: "moderate" },
    basePersona,
  );

  expect(result.motion).toBe("working");
  expect(result.expression).toBe("relaxed");
  expect(result.lookAt).toBe("focused");
});
