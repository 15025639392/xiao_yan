import { render, screen } from "@testing-library/react";

import { WorldPanel } from "./WorldPanel";


test("renders focus stage and step for the inner world", () => {
  render(
    <WorldPanel
      world={{
        time_of_day: "afternoon",
        energy: "high",
        mood: "calm",
        focus_tension: "medium",
        focus_stage: "consolidate",
        focus_step: 3,
      }}
    />
  );

  expect(screen.getByText("内在世界")).toBeInTheDocument();
  expect(screen.getByText("收束中")).toBeInTheDocument();
  expect(screen.getByText("第 3 步")).toBeInTheDocument();
});


test("does not render a fake focus label when there is no active focus stage", () => {
  render(
    <WorldPanel
      world={{
        time_of_day: "night",
        energy: "low",
        mood: "tired",
        focus_tension: "low",
        focus_stage: "none",
        focus_step: null,
      }}
    />
  );

  expect(screen.queryByText("无专注阶段")).not.toBeInTheDocument();
  expect(screen.queryByText(/第 .* 步/)).not.toBeInTheDocument();
});
