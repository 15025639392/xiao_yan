import { render, screen } from "@testing-library/react";
import { MarkdownMessage } from "./MarkdownMessage";

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
