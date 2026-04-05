import { render, screen } from "@testing-library/react";

import { AutobioPanel } from "./AutobioPanel";


test("renders autobiographical entries", () => {
  render(
    <AutobioPanel
      entries={[
        "我最近像是一路从第1步走到第3步，开始学着把这些变化连成自己的经历。",
      ]}
    />
  );

  expect(screen.getByText("自我叙事")).toBeInTheDocument();
  expect(
    screen.getByText("我最近像是一路从第1步走到第3步，开始学着把这些变化连成自己的经历。"),
  ).toBeInTheDocument();
});


test("renders empty autobiographical state", () => {
  render(<AutobioPanel entries={[]} />);

  expect(screen.getByText("还没有形成自我叙事。")).toBeInTheDocument();
});


test("deduplicates repeated autobiographical entries in the panel", () => {
  render(
    <AutobioPanel
      entries={[
        "我最近像是一路从第1步走到第3步。",
        "我最近像是一路从第1步走到第3步。",
      ]}
    />
  );

  expect(screen.getAllByText("我最近像是一路从第1步走到第3步。")).toHaveLength(1);
});
