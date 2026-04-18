import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ChatEntry } from "../ChatPanel";
import type { AppRoute } from "../../lib/appRoutes";
import { fetchMessages } from "../../lib/api";
import { syncMessagesFromRuntime } from "./chatRuntimeMessages";

type UseChatRouteMessagesParams = {
  route: AppRoute;
  setMessages: Dispatch<SetStateAction<ChatEntry[]>>;
};

export function useChatRouteMessages({ route, setMessages }: UseChatRouteMessagesParams) {
  useEffect(() => {
    if (route !== "chat") {
      return;
    }

    let cancelled = false;
    void fetchMessages()
      .then((nextMessages) => {
        if (!cancelled) {
          setMessages((current) => syncMessagesFromRuntime(current, nextMessages.messages));
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("加载聊天消息失败:", err);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [route, setMessages]);
}
