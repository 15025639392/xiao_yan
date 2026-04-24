import { useEffect, useState } from "react";

import { fetchPersona, fetchState } from "../../lib/api";
import type { BeingState, PersonaProfile } from "../../lib/api";
import { subscribeAppRealtime } from "../../lib/realtime";
import { getPersonaProfileFromRealtimeEvent } from "../app/runtimeSync";
import { getRuntimeRealtimePayload } from "../app/runtimeRealtimeUpdates";
import { AvatarStage } from "./AvatarStage";
import { getStoredAvatarPreviewModelUrl } from "./avatarPreviewModel";

const initialWindowState: BeingState = {
  mode: "sleeping",
  focus_mode: "sleeping",
  current_thought: null,
  active_goal_ids: [],
};

export function AvatarWindow() {
  const [state, setState] = useState<BeingState>(initialWindowState);
  const [persona, setPersona] = useState<PersonaProfile | null>(null);
  const [error, setError] = useState("");
  const [modelUrl, setModelUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialState() {
      try {
        const [nextState, nextPersona] = await Promise.all([fetchState(), fetchPersona()]);
        if (cancelled) return;
        setState(nextState);
        setPersona(nextPersona);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "小晏外显状态同步失败");
        }
      }
    }

    void loadInitialState();
    void getStoredAvatarPreviewModelUrl().then((url) => {
      if (!cancelled && url) setModelUrl(url);
    });

    const onPreviewModelChanged = () => {
      void getStoredAvatarPreviewModelUrl().then((url) => {
        if (!cancelled) setModelUrl(url);
      });
    };
    window.addEventListener("xiaoyan:avatar-preview-model-changed", onPreviewModelChanged);

    const unsubscribe = subscribeAppRealtime((event) => {
      if (cancelled) return;

      const runtimePayload = getRuntimeRealtimePayload(event);
      if (runtimePayload) {
        setState(runtimePayload.state);
      }

      const personaProfile = getPersonaProfileFromRealtimeEvent(event);
      if (personaProfile) {
        setPersona(personaProfile);
      }
    });

    return () => {
      cancelled = true;
      window.removeEventListener("xiaoyan:avatar-preview-model-changed", onPreviewModelChanged);
      unsubscribe();
    };
  }, []);

  return (
    <main className="avatar-window" data-tauri-drag-region>
      <AvatarStage state={state} persona={persona} modelUrl={modelUrl ?? undefined} />
      {error ? <p className="avatar-window__error">{error}</p> : null}
    </main>
  );
}
