import { useCallback } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ChatEntry } from "../ChatPanel";
import { syncMessagesFromRuntime } from "./chatRuntimeMessages";
import type { BeingState, Goal, InnerWorldState } from "../../lib/api";
import { fetchGoals, fetchMessages, fetchState, fetchWorld, sleep, updateGoalStatus, wake } from "../../lib/api";

type UseAppStateMutationsParams = {
  setError: Dispatch<SetStateAction<string>>;
  setGoals: Dispatch<SetStateAction<Goal[]>>;
  setMessages: Dispatch<SetStateAction<ChatEntry[]>>;
  setState: Dispatch<SetStateAction<BeingState>>;
  setWorld: Dispatch<SetStateAction<InnerWorldState | null>>;
  updateFocusTransitionHint: (nextState: BeingState) => void;
};

export function useAppStateMutations({
  setError,
  setGoals,
  setMessages,
  setState,
  setWorld,
  updateFocusTransitionHint,
}: UseAppStateMutationsParams) {
  const handleWake = useCallback(async () => {
    try {
      setError("");
      setState(await wake());
    } catch (err) {
      setError(err instanceof Error ? err.message : "唤醒失败");
    }
  }, [setError, setState]);

  const handleSleep = useCallback(async () => {
    try {
      setError("");
      setState(await sleep());
    } catch (err) {
      setError(err instanceof Error ? err.message : "休眠失败");
    }
  }, [setError, setState]);

  const handleUpdateGoalStatus = useCallback(
    async (goalId: string, status: Goal["status"]) => {
      try {
        setError("");
        const updatedGoal = await updateGoalStatus(goalId, status);
        const refreshedState = await fetchState();

        setGoals((current) =>
          current.map((goal) => (goal.id === updatedGoal.id ? updatedGoal : goal)),
        );
        updateFocusTransitionHint(refreshedState);
        setState(refreshedState);
      } catch (err) {
        setError(err instanceof Error ? err.message : "目标状态更新失败");
      }
    },
    [setError, setGoals, setState, updateFocusTransitionHint],
  );

  const handlePersonaUpdated = useCallback(async () => {
    try {
      const [nextState, nextMessages, nextGoals, nextWorld] = await Promise.all([
        fetchState(),
        fetchMessages(),
        fetchGoals(),
        fetchWorld(),
      ]);

      updateFocusTransitionHint(nextState);
      setState(nextState);
      setMessages(syncMessagesFromRuntime([], nextMessages.messages));
      setGoals(nextGoals.goals);
      setWorld(nextWorld);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "同步失败");
    }
  }, [setError, setGoals, setMessages, setState, setWorld, updateFocusTransitionHint]);

  return {
    handleWake,
    handleSleep,
    handleUpdateGoalStatus,
    handlePersonaUpdated,
  };
}
