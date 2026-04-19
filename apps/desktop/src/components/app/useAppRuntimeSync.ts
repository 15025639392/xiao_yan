import { useEffect } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";

import type { ChatEntry } from "../ChatPanel";
import type { PendingChatRequest } from "./chatRequestKey";
import {
  applyInitialRuntimeData,
  handleChatRealtimeEvent,
  handlePersonaRealtimeEvent,
  handleRuntimeRealtimeEvent,
} from "./appRuntimeSyncHandlers";
import { loadInitialRuntimeData } from "./runtimeSync";
import type { BeingState, PersonaProfile } from "../../lib/api";
import { subscribeAppRealtime } from "../../lib/realtime";
import { resolveRoute } from "../../lib/appRoutes";

type UseAppRuntimeSyncParams = {
  messagesRef: MutableRefObject<ChatEntry[]>;
  pendingRequestMessageRef: MutableRefObject<PendingChatRequest | null>;
  setError: Dispatch<SetStateAction<string>>;
  setIsSending: Dispatch<SetStateAction<boolean>>;
  setMessages: Dispatch<SetStateAction<ChatEntry[]>>;
  setPersona: Dispatch<SetStateAction<PersonaProfile | null>>;
  setState: Dispatch<SetStateAction<BeingState>>;
};

export function useAppRuntimeSync({
  messagesRef,
  pendingRequestMessageRef,
  setError,
  setIsSending,
  setMessages,
  setPersona,
  setState,
}: UseAppRuntimeSyncParams) {
  useEffect(() => {
    let cancelled = false;

    async function syncRuntime() {
      try {
        const initialRoute = resolveRoute(window.location.hash);
        const initialRuntime = await loadInitialRuntimeData(initialRoute);

        if (cancelled) {
          return;
        }

        applyInitialRuntimeData(initialRuntime, messagesRef, {
          setMessages,
          setState,
        });
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "同步失败");
        }
      }
    }

    void syncRuntime();

    const unsubscribeRuntime = subscribeAppRealtime((event) => {
      if (cancelled) {
        return;
      }

      if (
        handleChatRealtimeEvent(event, messagesRef, pendingRequestMessageRef, {
          setError,
          setIsSending,
          setMessages,
        })
      ) {
        return;
      }

      handleRuntimeRealtimeEvent(
        event,
        messagesRef,
        {
          setError,
          setIsSending,
          setMessages,
          setState,
        },
      );
    });

    const unsubscribePersona = subscribeAppRealtime((event) => {
      if (cancelled) {
        return;
      }

      handlePersonaRealtimeEvent(event, { setPersona });
    });

    return () => {
      cancelled = true;
      unsubscribeRuntime();
      unsubscribePersona();
    };
  }, [
    messagesRef,
    pendingRequestMessageRef,
    setError,
    setIsSending,
    setMessages,
    setPersona,
    setState,
  ]);
}
