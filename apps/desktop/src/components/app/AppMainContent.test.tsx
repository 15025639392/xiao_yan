import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { BeingState, PersonaProfile } from "../../lib/api";
import { AppMainContent } from "./AppMainContent";

vi.mock("../PersonaPanel", () => ({
  PersonaPanel: () => <div data-testid="persona-panel">persona</div>,
}));

vi.mock("../ChatPanel", () => ({
  ChatPanel: () => <div>chat</div>,
}));
vi.mock("../ToolPanel", () => ({
  ToolPanel: () => <div>tools</div>,
}));
vi.mock("../../pages/MemoryPage", () => ({
  MemoryPage: () => <div>memory</div>,
}));
vi.mock("../../pages/XiaohongshuPage", () => ({
  XiaohongshuPage: () => <div>xiaohongshu</div>,
}));
vi.mock("../../pages/CreativeWritingPage", () => ({
  CreativeWritingPage: () => <div>creative-writing</div>,
}));
vi.mock("../../pages/UpgradeProposalsPage", () => ({
  UpgradeProposalsPage: () => <div>upgrade-proposals</div>,
}));

const state: BeingState = {
  mode: "awake",
  focus_mode: "autonomy",
  current_thought: null,
  active_goal_ids: [],
};

const persona = {
  name: "小晏",
} as PersonaProfile;

test("renders persona panel for persona route", () => {
  render(
    <AppMainContent
      assistantName="小晏"
      attachedFiles={[]}
      attachedFolders={[]}
      attachedImages={[]}
      draft=""
      focusGoalTitle={null}
      focusContext={null}
      isSending={false}
      messages={[]}
      persona={persona}
      route="persona"
      state={state}
      onDraftChange={() => undefined}
      onPersonaUpdated={() => undefined}
      onPickFile={() => undefined}
      onPickFolder={() => undefined}
      onPickImage={() => undefined}
      onRemoveAttachedFile={() => undefined}
      onRemoveAttachedFolder={() => undefined}
      onRemoveAttachedImage={() => undefined}
      onResume={() => undefined}
      onRetry={() => undefined}
      onSend={() => undefined}
    />,
  );

  expect(screen.getByTestId("persona-panel")).toBeInTheDocument();
});

test("renders creative writing page for creative-writing route", () => {
  render(
    <AppMainContent
      assistantName="小晏"
      attachedFiles={[]}
      attachedFolders={[]}
      attachedImages={[]}
      draft=""
      focusGoalTitle={null}
      focusContext={null}
      isSending={false}
      messages={[]}
      persona={persona}
      route="creative-writing"
      state={state}
      onDraftChange={() => undefined}
      onPersonaUpdated={() => undefined}
      onPickFile={() => undefined}
      onPickFolder={() => undefined}
      onPickImage={() => undefined}
      onRemoveAttachedFile={() => undefined}
      onRemoveAttachedFolder={() => undefined}
      onRemoveAttachedImage={() => undefined}
      onResume={() => undefined}
      onRetry={() => undefined}
      onSend={() => undefined}
    />,
  );

  expect(screen.getByText("creative-writing")).toBeInTheDocument();
});

test("renders upgrade proposals page for upgrade-proposals route", () => {
  render(
    <AppMainContent
      assistantName="小晏"
      attachedFiles={[]}
      attachedFolders={[]}
      attachedImages={[]}
      draft=""
      focusGoalTitle={null}
      focusContext={null}
      isSending={false}
      messages={[]}
      persona={persona}
      route="upgrade-proposals"
      state={state}
      onDraftChange={() => undefined}
      onPersonaUpdated={() => undefined}
      onPickFile={() => undefined}
      onPickFolder={() => undefined}
      onPickImage={() => undefined}
      onRemoveAttachedFile={() => undefined}
      onRemoveAttachedFolder={() => undefined}
      onRemoveAttachedImage={() => undefined}
      onResume={() => undefined}
      onRetry={() => undefined}
      onSend={() => undefined}
    />,
  );

  expect(screen.getByText("upgrade-proposals")).toBeInTheDocument();
});
