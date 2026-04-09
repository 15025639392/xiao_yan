import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import type { ChatEntry } from "./chatTypes";

const AUTO_SCROLL_THRESHOLD_PX = 48;

function buildMessageContentHash(messages: ChatEntry[]) {
  return messages.map((msg) => `${msg.id}-${msg.role}-${msg.content}-${msg.state ?? ""}`).join("|");
}

function isNearBottom(container: HTMLDivElement) {
  const distanceFromBottom = container.scrollHeight - container.clientHeight - container.scrollTop;
  return distanceFromBottom <= AUTO_SCROLL_THRESHOLD_PX;
}

type UseChatScrollBehaviorProps = {
  messages: ChatEntry[];
  isSending: boolean;
  messagesContainerRef: RefObject<HTMLDivElement>;
  messagesEndRef: RefObject<HTMLDivElement>;
};

export function useChatScrollBehavior({
  messages,
  isSending,
  messagesContainerRef,
  messagesEndRef,
}: UseChatScrollBehaviorProps) {
  const savedScrollRef = useRef<{ scrollTop: number; contentHash: string } | null>(null);
  const wasVisibleRef = useRef(false);
  const autoScrollEnabledRef = useRef(true);
  const previousContentHashRef = useRef("");
  const previousIsSendingRef = useRef(isSending);
  const latestContentHashRef = useRef(buildMessageContentHash(messages));
  latestContentHashRef.current = buildMessageContentHash(messages);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    function handleVisibilityChange() {
      if (document.hidden) {
        savedScrollRef.current = {
          scrollTop: container.scrollTop,
          contentHash: latestContentHashRef.current,
        };
        wasVisibleRef.current = false;
      } else if (!wasVisibleRef.current) {
        wasVisibleRef.current = true;
        const saved = savedScrollRef.current;
        const currentHash = latestContentHashRef.current;

        if (saved && saved.contentHash === currentHash) {
          container.scrollTop = saved.scrollTop;
        }

        autoScrollEnabledRef.current = isNearBottom(container);
      }
    }

    wasVisibleRef.current = !document.hidden;
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [messagesContainerRef]);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    autoScrollEnabledRef.current = isNearBottom(container);

    function handleScroll() {
      autoScrollEnabledRef.current = isNearBottom(container);
    }

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", handleScroll);
    };
  }, [messagesContainerRef]);

  useEffect(() => {
    if (document.hidden) return;

    const currentHash = latestContentHashRef.current;
    const contentChanged = previousContentHashRef.current !== currentHash;
    const startedSending = !previousIsSendingRef.current && isSending;
    const shouldAutoScroll = autoScrollEnabledRef.current || startedSending;

    previousContentHashRef.current = currentHash;
    previousIsSendingRef.current = isSending;

    if (!contentChanged && !startedSending) return;
    if (!shouldAutoScroll) return;

    requestAnimationFrame(() => {
      if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === "function") {
        try {
          messagesEndRef.current.scrollIntoView({ behavior: startedSending ? "smooth" : "auto" });
        } catch {
          // ignore in test environments
        }
      }
    });
  }, [messages, isSending, messagesContainerRef, messagesEndRef]);
}
