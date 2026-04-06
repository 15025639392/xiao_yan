import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import type { ChatEntry } from "./chatTypes";

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

  function getMessageContentHash() {
    return messages.map((msg) => `${msg.id}-${msg.role}-${msg.content}-${msg.state}`).join("|");
  }

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    function handleVisibilityChange() {
      if (document.hidden) {
        savedScrollRef.current = {
          scrollTop: container.scrollTop,
          contentHash: getMessageContentHash(),
        };
        wasVisibleRef.current = false;
      } else if (!wasVisibleRef.current) {
        wasVisibleRef.current = true;
        const saved = savedScrollRef.current;
        const currentHash = getMessageContentHash();

        if (saved && saved.contentHash === currentHash) {
          container.scrollTop = saved.scrollTop;
        }
      }
    }

    wasVisibleRef.current = !document.hidden;
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [messages, messagesContainerRef]);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const currentHash = getMessageContentHash();
    const saved = savedScrollRef.current;
    const contentChanged = !saved || saved.contentHash !== currentHash;

    if ((contentChanged || isSending) && !document.hidden) {
      requestAnimationFrame(() => {
        if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === "function") {
          try {
            messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
          } catch {
            // ignore in test environments
          }
        }
      });
    }
  }, [messages, isSending, messagesContainerRef, messagesEndRef]);
}
