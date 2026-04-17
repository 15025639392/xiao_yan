import { fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { useRef } from "react";
import type { ChatEntry } from "./chatTypes";
import { useChatScrollBehavior } from "./useChatScrollBehavior";

type ScrollHarnessProps = {
  messages: ChatEntry[];
  isSending: boolean;
};

function ScrollHarness({ messages, isSending }: ScrollHarnessProps) {
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useChatScrollBehavior({
    messages,
    isSending,
    messagesContainerRef,
    messagesEndRef,
  });

  return (
    <div ref={messagesContainerRef} data-testid="messages-container">
      <div ref={messagesEndRef} />
    </div>
  );
}

function setContainerMetrics(
  container: HTMLDivElement,
  metrics: { scrollTop: number; clientHeight: number; scrollHeight: number },
) {
  Object.defineProperty(container, "scrollTop", {
    configurable: true,
    writable: true,
    value: metrics.scrollTop,
  });
  Object.defineProperty(container, "clientHeight", {
    configurable: true,
    value: metrics.clientHeight,
  });
  Object.defineProperty(container, "scrollHeight", {
    configurable: true,
    value: metrics.scrollHeight,
  });
}

const baseMessages: ChatEntry[] = [
  { id: "1", role: "user", content: "你好" },
  { id: "2", role: "assistant", content: "我在" },
];

let scrollIntoViewMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  scrollIntoViewMock = vi.fn();
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    writable: true,
    value: scrollIntoViewMock,
  });
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    callback(0);
    return 1;
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("does not auto-scroll when user has scrolled away from the bottom", () => {
  const { getByTestId, rerender } = render(<ScrollHarness messages={baseMessages} isSending={false} />);
  const container = getByTestId("messages-container") as HTMLDivElement;

  setContainerMetrics(container, {
    scrollTop: 200,
    clientHeight: 400,
    scrollHeight: 1200,
  });
  fireEvent.scroll(container);

  scrollIntoViewMock.mockClear();

  rerender(
    <ScrollHarness
      messages={[...baseMessages, { id: "3", role: "assistant", content: "这是新增消息" }]}
      isSending={false}
    />,
  );

  expect(scrollIntoViewMock).not.toHaveBeenCalled();
});

test("auto-scrolls when user is near the bottom", () => {
  const { getByTestId, rerender } = render(<ScrollHarness messages={baseMessages} isSending={false} />);
  const container = getByTestId("messages-container") as HTMLDivElement;

  setContainerMetrics(container, {
    scrollTop: 760,
    clientHeight: 400,
    scrollHeight: 1200,
  });
  fireEvent.scroll(container);

  scrollIntoViewMock.mockClear();

  rerender(
    <ScrollHarness
      messages={[...baseMessages, { id: "3", role: "assistant", content: "这是新增消息" }]}
      isSending={false}
    />,
  );

  expect(scrollIntoViewMock).toHaveBeenCalledTimes(1);
});

test("does not force-scroll when sending starts while user is reading older messages", () => {
  const { getByTestId, rerender } = render(<ScrollHarness messages={baseMessages} isSending={false} />);
  const container = getByTestId("messages-container") as HTMLDivElement;

  setContainerMetrics(container, {
    scrollTop: 180,
    clientHeight: 400,
    scrollHeight: 1200,
  });
  fireEvent.scroll(container);

  scrollIntoViewMock.mockClear();

  rerender(<ScrollHarness messages={baseMessages} isSending={true} />);

  expect(scrollIntoViewMock).not.toHaveBeenCalled();
});

test("still scrolls when sending starts near the bottom", () => {
  const { getByTestId, rerender } = render(<ScrollHarness messages={baseMessages} isSending={false} />);
  const container = getByTestId("messages-container") as HTMLDivElement;

  setContainerMetrics(container, {
    scrollTop: 760,
    clientHeight: 400,
    scrollHeight: 1200,
  });
  fireEvent.scroll(container);

  scrollIntoViewMock.mockClear();

  rerender(<ScrollHarness messages={baseMessages} isSending={true} />);

  expect(scrollIntoViewMock).toHaveBeenCalledTimes(1);
});
