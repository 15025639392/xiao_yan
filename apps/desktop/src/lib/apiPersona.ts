import { get, post, put } from "./apiClient";

export type EmotionType =
  | "joy" | "sadness" | "anger" | "fear" | "surprise"
  | "disgust" | "calm" | "engaged" | "proud" | "lonely"
  | "grateful" | "frustrated";

export type EmotionIntensity = "none" | "mild" | "moderate" | "strong" | "intense";

export type FormalLevel = "very_formal" | "formal" | "neutral" | "casual" | "slangy";

export type ExpressionHabit = "metaphor" | "direct" | "questioning" | "humorous" | "gentle";

export type SentenceStyleType = "short" | "mixed" | "long";

export type PersonaProfile = {
  name: string;
  identity: string;
  origin_story: string;
  features: {
    avatar_enabled: boolean;
  };
  personality: {
    openness: number;
    conscientiousness: number;
    extraversion: number;
    agreeableness: number;
    neuroticism: number;
  };
  speaking_style: {
    formal_level: FormalLevel;
    sentence_style: SentenceStyleType;
    expression_habit: ExpressionHabit;
    emoji_usage: string;
    verbal_tics: string[];
    response_length: string;
  };
  values: {
    core_values: { name: string; description: string; priority: number }[];
    boundaries: string[];
  };
  emotion: {
    primary_emotion: EmotionType;
    primary_intensity: EmotionIntensity;
    secondary_emotion: EmotionType | null;
    secondary_intensity: EmotionIntensity;
    mood_valence: number;
    arousal: number;
    is_calm: boolean;
    active_entry_count: number;
    active_entries: Array<{
      emotion_type: EmotionType;
      intensity: EmotionIntensity;
      reason: string;
      source: string;
    }>;
    last_updated: string | null;
  };
  version: number;
};

export type EmotionState = {
  primary_emotion: EmotionType;
  primary_intensity: EmotionIntensity;
  secondary_emotion: EmotionType | null;
  secondary_intensity: EmotionIntensity;
  mood_valence: number;
  arousal: number;
  is_calm: boolean;
  active_entry_count: number;
  active_entries: Array<{
    emotion_type: EmotionType;
    intensity: EmotionIntensity;
    reason: string;
    source: string;
  }>;
  last_updated: string | null;
};

export function fetchPersona(): Promise<PersonaProfile> {
  return get<PersonaProfile>("/persona");
}

export function fetchEmotionState(): Promise<EmotionState> {
  return get<EmotionState>("/persona/emotion");
}

export function updatePersona(data: {
  name?: string;
  identity?: string;
  origin_story?: string;
}): Promise<{ success: boolean; profile: PersonaProfile }> {
  return put<{ success: boolean; profile: PersonaProfile }>("/persona", data);
}

export function updatePersonality(data: {
  openness?: number;
  conscientiousness?: number;
  extraversion?: number;
  agreeableness?: number;
  neuroticism?: number;
}): Promise<{ success: boolean; profile: PersonaProfile }> {
  return put<{ success: boolean; profile: PersonaProfile }>("/persona/personality", data);
}

export function updateSpeakingStyle(data: {
  formal_level?: FormalLevel;
  sentence_style?: SentenceStyleType;
  expression_habit?: ExpressionHabit;
  emoji_usage?: string;
  verbal_tics?: string[];
  response_length?: string;
}): Promise<{ success: boolean; profile: PersonaProfile }> {
  return put<{ success: boolean; profile: PersonaProfile }>("/persona/speaking-style", data);
}

export function updatePersonaFeatures(data: {
  avatar_enabled?: boolean;
}): Promise<{ success: boolean; profile: PersonaProfile }> {
  return put<{ success: boolean; profile: PersonaProfile }>("/persona/features", data);
}

export function resetPersona(): Promise<{ success: boolean; profile: PersonaProfile }> {
  return post<{ success: boolean; profile: PersonaProfile }>("/persona/reset");
}

export function initializePersona(): Promise<{
  success: boolean;
  message: string;
  cleared: { memories: number; goals: number };
  profile: PersonaProfile;
}> {
  return post<{
    success: boolean;
    message: string;
    cleared: { memories: number; goals: number };
    profile: PersonaProfile;
  }>("/persona/initialize");
}
