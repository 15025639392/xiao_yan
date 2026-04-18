import { useCallback, useRef, useState } from "react";

import type { BeingState, Goal } from "../../lib/api";
import { deriveFocusTransitionHint, shouldRefreshFocusTransitionHint } from "./focusTransition";

export function useFocusPresentation(state: BeingState, goals: Goal[]) {
  const [focusTransitionHint, setFocusTransitionHint] = useState<string | null>(null);
  const stateRef = useRef<BeingState>(state);
  stateRef.current = state;

  const focusContext = state.focus_context ?? null;
  const focusGoalTitle = resolveFocusGoalTitle(state, goals);
  const focusContextSummary = focusContext?.prompt_summary ?? null;

  const updateFocusTransitionHint = useCallback((nextState: BeingState) => {
    setFocusTransitionHint((current) =>
      shouldRefreshFocusTransitionHint(stateRef.current, nextState)
        ? deriveFocusTransitionHint(stateRef.current, nextState)
        : current,
    );
  }, []);

  return {
    focusContext,
    focusGoalTitle,
    focusContextSummary,
    focusTransitionHint,
    updateFocusTransitionHint,
  };
}

function resolveFocusGoalTitle(state: BeingState, goals: Goal[]): string | null {
  if (state.active_goal_ids.length > 0) {
    const currentGoal = goals.find((goal) => goal.id === state.active_goal_ids[0]);
    if (currentGoal) {
      return currentGoal.title;
    }
  }

  return state.today_plan?.goal_title ?? null;
}
