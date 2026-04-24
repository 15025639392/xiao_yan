import { useEffect, useMemo, useRef, useState } from "react";

import type { BeingState, PersonaProfile } from "../../lib/api";
import { mapAvatarState } from "./avatarStateMapper";
import type { VrmRuntime } from "./vrm/VrmRuntime";

type AvatarStageProps = {
  state?: BeingState | null;
  persona: PersonaProfile | null;
  modelUrl?: string;
};

const DEFAULT_MODEL_URL = "/avatar/xiaoyan.vrm";

export function AvatarStage({ state, persona, modelUrl = DEFAULT_MODEL_URL }: AvatarStageProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const runtimeRef = useRef<VrmRuntime | null>(null);
  const [runtimeMessage, setRuntimeMessage] = useState<string | null>(null);
  const renderStateRef = useRef<ReturnType<typeof mapAvatarState> | null>(null);
  const safeState = state ?? fallbackState();
  const renderState = useMemo(
    () => mapAvatarState(safeState, persona?.emotion ?? fallbackEmotion(), persona),
    [persona, safeState],
  );

  useEffect(() => {
    renderStateRef.current = renderState;
    runtimeRef.current?.applyState(renderState);
  }, [renderState]);

  useEffect(() => {
    if (!containerRef.current) return;
    if (!hasWebGLSupport()) {
      setRuntimeMessage("当前环境不支持 WebGL，已保留状态预览。");
      return;
    }

    setRuntimeMessage(null);
    let cancelled = false;
    let runtime: VrmRuntime | null = null;
    const onResize = () => runtime?.resize();

    void import("./vrm/VrmRuntime").then(({ VrmRuntime }) => {
      if (cancelled || !containerRef.current) return;

      runtime = new VrmRuntime({
        container: containerRef.current,
        modelUrl,
        onError: (message) => setRuntimeMessage(`模型未加载：${message}`),
      });
      runtimeRef.current = runtime;
      if (renderStateRef.current) {
        runtime.applyState(renderStateRef.current);
      }
      void runtime.start();
      window.addEventListener("resize", onResize);
    });

    return () => {
      cancelled = true;
      window.removeEventListener("resize", onResize);
      runtime?.dispose();
      if (runtimeRef.current === runtime) {
        runtimeRef.current = null;
      }
    };
  }, [modelUrl]);

  return (
    <section className="avatar-stage" aria-label="VRM 外显状态">
      <div ref={containerRef} className="avatar-stage__canvas" />
      {runtimeMessage ? <p className="avatar-stage__notice">{runtimeMessage}</p> : null}
    </section>
  );
}

function fallbackEmotion(): PersonaProfile["emotion"] {
  return {
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
}

function fallbackState(): BeingState {
  return {
    mode: "sleeping",
    focus_mode: "sleeping",
    current_thought: null,
    active_goal_ids: [],
  };
}

function hasWebGLSupport(): boolean {
  if (typeof document === "undefined") return false;
  if (typeof navigator !== "undefined" && navigator.userAgent.includes("jsdom")) return false;
  const canvas = document.createElement("canvas");
  try {
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}
