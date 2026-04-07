import { render, screen } from "@testing-library/react";

import { MemoryRelationshipSummary } from "./MemoryRelationshipSummary";

test("renders relationship summary sections when relationship state exists", () => {
  render(
    <MemoryRelationshipSummary
      relationship={{
        available: true,
        boundaries: ["别催我，我希望先自己想一想再决定"],
        commitments: ["答应你明天提醒你复盘"],
        preferences: ["喜欢先看方案再做决定"],
      }}
    />,
  );

  expect(screen.getByText("关系状态")).toBeInTheDocument();
  expect(screen.getByText("相处边界")).toBeInTheDocument();
  expect(screen.getByText("别催我，我希望先自己想一想再决定")).toBeInTheDocument();
  expect(screen.getByText("对用户承诺")).toBeInTheDocument();
  expect(screen.getByText("答应你明天提醒你复盘")).toBeInTheDocument();
  expect(screen.getByText("用户偏好")).toBeInTheDocument();
  expect(screen.getByText("喜欢先看方案再做决定")).toBeInTheDocument();
});

test("does not render when relationship state is unavailable", () => {
  const { container } = render(
    <MemoryRelationshipSummary
      relationship={{
        available: false,
        boundaries: [],
        commitments: [],
        preferences: [],
      }}
    />,
  );

  expect(container.firstChild).toBeNull();
});
