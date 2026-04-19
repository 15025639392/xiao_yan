import { useRef } from "react";

import type { BeingState } from "../../lib/api";

export function useFocusPresentation(state: BeingState) {
  const stateRef = useRef<BeingState>(state);
  stateRef.current = state;

  const focusContext = state.focus_context ?? null;
  const focusGoalTitle = resolveFocusGoalTitle(state);

  return {
    focusContext,
    focusGoalTitle,
  };
}

function resolveFocusGoalTitle(state: BeingState): string | null {
  const focusSubjectTitle = state.focus_subject?.title?.trim();
  if (focusSubjectTitle) {
    return focusSubjectTitle;
  }

  return null;
}
