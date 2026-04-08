import { render, screen, within } from "@testing-library/react";

import { ChatMessages } from "./ChatMessages";

test("shows response reference only on the latest assistant message", () => {
  const { container } = render(
    <ChatMessages
      assistantName="小晏"
      messages={[
        { id: "user-1", role: "user", content: "你好" },
        { id: "assistant-1", role: "assistant", content: "我在听。" },
        { id: "assistant-2", role: "assistant", content: "我更想先把真实判断告诉你。" },
      ]}
      relationship={{
        available: true,
        boundaries: ["先直接给真实判断"],
        commitments: ["答应你先提示风险"],
        preferences: ["喜欢一起推演"],
      }}
      isSending={false}
      showMemoryContext={new Set()}
      onToggleMemoryContext={() => {}}
      onDraftChange={() => {}}
    />,
  );

  expect(screen.getAllByText("本次回应参考")).toHaveLength(1);

  const assistantMessages = container.querySelectorAll(".chat-message--assistant");
  expect(assistantMessages).toHaveLength(2);
  expect(within(assistantMessages[0] as HTMLElement).queryByText("本次回应参考")).toBeNull();
  expect(within(assistantMessages[1] as HTMLElement).getByText("本次回应参考")).toBeInTheDocument();
});
