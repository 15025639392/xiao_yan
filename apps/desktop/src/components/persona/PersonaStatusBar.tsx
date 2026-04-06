import { useEffect, useState } from "react";
import type { PersonaProfile } from "../../lib/api";
import { fetchEmotionState, fetchPersona } from "../../lib/api";
import { subscribeAppRealtime } from "../../lib/realtime";
import { getEmotionDisplay, moodBarColor } from "./personaUtils";

type EmotionOverview = {
  primary_emotion: string;
  primary_intensity: string;
  mood_valence: number;
};

export function PersonaStatusBar() {
  const [profile, setProfile] = useState<PersonaProfile | null>(null);
  const [emotion, setEmotion] = useState<EmotionOverview | null>(null);

  useEffect(() => {
    void loadStatus(setProfile, setEmotion);
    const unsubscribe = subscribeAppRealtime((event) => {
      const personaPayload =
        event.type === "snapshot" ? event.payload.persona : event.type === "persona_updated" ? event.payload : null;
      if (!personaPayload) {
        return;
      }
      setProfile(personaPayload.profile);
      setEmotion(personaPayload.emotion);
    });
    return () => unsubscribe();
  }, []);

  if (!profile || !emotion) {
    return (
      <div className="persona-status-bar persona-status-bar--loading">
        <div className="persona-status-bar__skeleton" />
      </div>
    );
  }

  const emotionConfig = getEmotionDisplay(emotion.primary_emotion, emotion.primary_intensity);
  const moodPercent = ((emotion.mood_valence + 1) / 2) * 100;

  return (
    <div className="persona-status-bar">
      <div className="persona-status-bar__item">
        <span className="persona-status-bar__label">名字</span>
        <span className="persona-status-bar__value">{profile.name}</span>
      </div>
      <div className="persona-status-bar__divider" />
      <div className="persona-status-bar__item">
        <span className="persona-status-bar__label">身份</span>
        <span className="persona-status-bar__value">{profile.identity}</span>
      </div>
      <div className="persona-status-bar__divider" />
      <div className="persona-status-bar__item">
        <span className="persona-status-bar__label">当前情绪</span>
        <span
          className="persona-status-bar__emotion"
          style={{
            color: emotionConfig.color,
            borderColor: emotionConfig.color,
          }}
        >
          {emotionConfig.emoji} {emotionConfig.label}
        </span>
      </div>
      <div className="persona-status-bar__divider" />
      <div className="persona-status-bar__item persona-status-bar__item--grow">
        <span className="persona-status-bar__label">心情值</span>
        <div className="persona-status-bar__mood">
          <div className="persona-status-bar__mood-track">
            <div
              className="persona-status-bar__mood-fill"
              style={{
                width: `${moodPercent}%`,
                background: moodBarColor(moodPercent),
              }}
            />
          </div>
          <span className="persona-status-bar__mood-value">{emotion.mood_valence.toFixed(1)}</span>
        </div>
      </div>
    </div>
  );
}

async function loadStatus(
  setProfile: (profile: PersonaProfile) => void,
  setEmotion: (emotion: EmotionOverview) => void,
) {
  try {
    const [profile, emotion] = await Promise.all([fetchPersona(), fetchEmotionState()]);
    setProfile(profile);
    setEmotion(emotion);
  } catch {
    // 静默失败
  }
}

