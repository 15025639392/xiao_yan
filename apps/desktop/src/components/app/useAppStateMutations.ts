import { useCallback } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ChatEntry } from "../ChatPanel";
import { syncMessagesFromRuntime } from "./chatRuntimeMessages";
import type { BeingState } from "../../lib/api";
import { fetchMessages, fetchState } from "../../lib/api";

type UseAppStateMutationsParams = {
  setError: Dispatch<SetStateAction<string>>;
  setMessages: Dispatch<SetStateAction<ChatEntry[]>>;
  setState: Dispatch<SetStateAction<BeingState>>;
};

export function useAppStateMutations({
  setError,
  setMessages,
  setState,
}: UseAppStateMutationsParams) {
  const handlePersonaUpdated = useCallback(async () => {
    try {
      const [nextState, nextMessages] = await Promise.all([
        fetchState(),
        fetchMessages(),
      ]);

      setState(nextState);
      setMessages(syncMessagesFromRuntime([], nextMessages.messages));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "同步失败");
    }
  }, [setError, setMessages, setState]);

  return {
    handlePersonaUpdated,
  };
}
