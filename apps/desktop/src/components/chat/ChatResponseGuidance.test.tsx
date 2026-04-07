import { render, screen } from "@testing-library/react";

import { ChatResponseGuidance } from "./ChatResponseGuidance";

test("renders response principles from relationship summary", () => {
  render(
    <ChatResponseGuidance
      relationship={{
        available: true,
        boundaries: ["先直接说真实判断"],
        commitments: ["答应你风险要前置说明"],
        preferences: ["更喜欢先听理由再定方案"],
      }}
    />,
  );

  expect(screen.getByText("本次回应原则")).toBeInTheDocument();
  expect(screen.getByText("先守住边界")).toBeInTheDocument();
  expect(screen.getByText("先直接说真实判断")).toBeInTheDocument();
  expect(screen.getByText("先兑现承诺")).toBeInTheDocument();
  expect(screen.getByText("答应你风险要前置说明")).toBeInTheDocument();
  expect(screen.getByText("尽量贴合偏好")).toBeInTheDocument();
  expect(screen.getByText("更喜欢先听理由再定方案")).toBeInTheDocument();
});

test("does not render when relationship summary is unavailable", () => {
  const { container } = render(
    <ChatResponseGuidance
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
