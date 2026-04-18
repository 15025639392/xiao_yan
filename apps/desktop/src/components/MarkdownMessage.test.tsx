import { render, screen } from "@testing-library/react";
import { MarkdownMessage } from "./MarkdownMessage";

test("preserves natural line breaks for plain multi-line replies", () => {
  const { container } = render(
    <MarkdownMessage
      content={"先给你结论\n再补一句原因\n\n最后提醒一个风险"}
    />,
  );

  expect(container.querySelectorAll("br")).toHaveLength(1);
  expect(container.querySelectorAll(".markdown-paragraph")).toHaveLength(2);
  expect(screen.getByText("最后提醒一个风险")).toBeInTheDocument();
});

test("renders markdown code blocks with a dedicated container", () => {
  const { container } = render(
    <MarkdownMessage
      content={"结论如下：\n\n```ts\nconst answer = {\n  status: 'ok',\n};\n```"}
    />,
  );

  expect(container.querySelector(".markdown-code-block")).not.toBeNull();
  expect(screen.getByText("ts")).toBeInTheDocument();
  expect(screen.getByText("结论如下：")).toBeInTheDocument();
});

test("promotes raw json payloads into a code-style block", () => {
  const { container } = render(
    <MarkdownMessage
      content={'{\n  "mode": "focus",\n  "path": "/tmp/workspace/project-a/README.md"\n}'}
    />,
  );

  expect(container.querySelector(".markdown-code-block")).not.toBeNull();
  expect(screen.getByText("json")).toBeInTheDocument();
  expect(screen.getByText(/"path":/)).toBeInTheDocument();
});

test("promotes multi-line config snippets into a code-style block", () => {
  const { container } = render(
    <MarkdownMessage
      content={"mode=focus\npath=/tmp/workspace/project-a/README.md\nretry=true"}
    />,
  );

  expect(container.querySelector(".markdown-code-block")).not.toBeNull();
  expect(screen.getByText("text")).toBeInTheDocument();
  expect(screen.getByText(/path=\/tmp\/workspace\/project-a\/README.md/)).toBeInTheDocument();
});
