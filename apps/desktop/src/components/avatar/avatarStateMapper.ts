import type { BeingState, EmotionState, PersonaProfile } from "../../lib/api";
import type { AvatarExpression, AvatarLookAt, AvatarMotion, AvatarRenderState } from "./avatarTypes";

const INTENSITY_WEIGHT: Record<EmotionState["primary_intensity"], number> = {
  none: 0,
  mild: 0.25,
  moderate: 0.55,
  strong: 0.85,
  intense: 1,
};

const EMOTION_EXPRESSION: Partial<Record<EmotionState["primary_emotion"], AvatarExpression>> = {
  joy: "happy",
  sadness: "sad",
  anger: "angry",
  fear: "sad",
  surprise: "surprised",
  calm: "neutral",
  engaged: "relaxed",
  proud: "happy",
  grateful: "happy",
  frustrated: "angry",
  lonely: "sad",
};

export function mapAvatarState(
  state: BeingState,
  emotion: EmotionState,
  persona: PersonaProfile | null,
): AvatarRenderState {
  if (state.mode === "sleeping") {
    return {
      motion: "sleeping",
      expression: "relaxed",
      expressionWeight: 0.7,
      lookAt: "down",
      motionEnergy: 0.15,
    };
  }

  const motion = mapFocusMotion(state.focus_mode);
  const expression = EMOTION_EXPRESSION[emotion.primary_emotion] ?? "neutral";
  const expressionWeight = expression === "neutral" ? 0 : INTENSITY_WEIGHT[emotion.primary_intensity];
  const motionEnergy = clampMotionEnergy(emotion.arousal, persona);

  return {
    motion,
    expression,
    expressionWeight,
    lookAt: mapLookAt(motion),
    motionEnergy,
  };
}

function mapFocusMotion(focusMode: BeingState["focus_mode"]): AvatarMotion {
  if (focusMode === "morning_plan") return "thinking";
  if (focusMode === "orchestrator") return "working";
  return "idle";
}

function mapLookAt(motion: AvatarMotion): AvatarLookAt {
  if (motion === "working") return "focused";
  if (motion === "thinking") return "away";
  return "user";
}

function clampMotionEnergy(arousal: number, persona: PersonaProfile | null): number {
  const extraversion = persona?.personality?.extraversion ?? 50;
  const personalityBoost = (extraversion - 50) / 250;
  return Math.max(0.1, Math.min(1, arousal + personalityBoost));
}
