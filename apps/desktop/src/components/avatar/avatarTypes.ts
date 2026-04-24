export type AvatarMotion = "idle" | "thinking" | "working" | "sleeping";

export type AvatarExpression = "neutral" | "happy" | "sad" | "angry" | "relaxed" | "surprised";

export type AvatarLookAt = "user" | "focused" | "down" | "away";

export type AvatarRenderState = {
  motion: AvatarMotion;
  expression: AvatarExpression;
  expressionWeight: number;
  lookAt: AvatarLookAt;
  motionEnergy: number;
};
