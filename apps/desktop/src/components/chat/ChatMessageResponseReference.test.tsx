import { render, screen } from "@testing-library/react";

import { ChatMessageResponseReference } from "./ChatMessageResponseReference";

test("prefers boundary as the primary response reference", () => {
  render(
    <ChatMessageResponseReference
      relationship={{
        available: true,
        boundaries: ["先直接给真实判断"],
        commitments: ["答应你先提示风险"],
        preferences: ["喜欢一起推演"],
      }}
    />,
  );

  expect(screen.getByText("本次回应参考")).toBeInTheDocument();
  expect(screen.getByText("先守住边界")).toBeInTheDocument();
  expect(screen.getByText("先直接给真实判断")).toBeInTheDocument();
});

test("falls back to commitment when no boundary exists", () => {
  render(
    <ChatMessageResponseReference
      relationship={{
        available: true,
        boundaries: [],
        commitments: ["答应你不装懂，会先说不确定性"],
        preferences: ["喜欢先讨论再行动"],
      }}
    />,
  );

  expect(screen.getByText("先兑现承诺")).toBeInTheDocument();
  expect(screen.getByText("答应你不装懂，会先说不确定性")).toBeInTheDocument();
});
