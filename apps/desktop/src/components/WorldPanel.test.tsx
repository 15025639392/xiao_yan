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

  expect(screen.getByText("此刻感受")).toBeInTheDocument();
  expect(screen.getByText("现在在收束中，已经走到第 3 步。")).toBeInTheDocument();
  expect(screen.getByText(/下午里，她的能量高、情绪偏平静/)).toBeInTheDocument();
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

test("prefers latest_event as the first summary line", () => {
  render(
    <WorldPanel
      world={{
        time_of_day: "night",
        energy: "low",
        mood: "tired",
        focus_tension: "low",
        focus_stage: "none",
        focus_step: null,
        latest_event: "夜里很安静，我有点困，但还惦记着今天没做完的事。",
      }}
    />
  );

  expect(screen.getByText("夜里很安静，我有点困，但还惦记着今天没做完的事。")).toBeInTheDocument();
});
