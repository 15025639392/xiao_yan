import type { BeingState, FocusContext } from "../../lib/api";
import { getFocusTransitionHint } from "../../lib/focusContextPresentation";

export function deriveFocusTransitionHint(
  previousState: BeingState | null,
  nextState: BeingState,
): string | null {
  const previousFocusContext = previousState?.focus_context ?? null;
  const nextFocusContext = nextState.focus_context ?? null;
  return getFocusTransitionHint(previousFocusContext, nextFocusContext);
}

export function shouldRefreshFocusTransitionHint(
  previousState: BeingState | null,
  nextState: BeingState,
): boolean {
  const previousFocusContext = previousState?.focus_context ?? null;
  const nextFocusContext = nextState.focus_context ?? null;

  if (!previousFocusContext && !nextFocusContext) {
    return false;
  }

  if (!previousFocusContext || !nextFocusContext) {
    return true;
  }

  return (
    previousFocusContext.goal_title !== nextFocusContext.goal_title ||
    previousFocusContext.source_kind !== nextFocusContext.source_kind ||
    previousFocusContext.reason_kind !== nextFocusContext.reason_kind ||
    previousFocusContext.reason_label !== nextFocusContext.reason_label
  );
}
