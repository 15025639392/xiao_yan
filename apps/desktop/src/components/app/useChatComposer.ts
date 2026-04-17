import { useCallback } from "react";

import type { Dispatch, MutableRefObject, SetStateAction } from "react";

import type { ChatEntry, ChatSendOptions } from "../ChatPanel";
import type { ChatAttachment, ChatRequestBody } from "../../lib/api";
import { chat, resumeChat } from "../../lib/api";
import { loadChatToolboxSelectedSkills } from "../../lib/chatToolboxPreferences";
import { createChatRequestKey } from "./chatRequestKey";
import type { PendingChatRequest } from "./chatRequestKey";

type UseChatComposerArgs = {
  attachedFiles: string[];
  attachedFolders: string[];
  attachedImages: string[];
  clearAttachments: () => void;
  restoreAttachments: (snapshot: {
    attachedFiles: string[];
    attachedFolders: string[];
    attachedImages: string[];
  }) => void;
  draft: string;
  pendingRequestMessageRef: MutableRefObject<PendingChatRequest | null>;
  setDraft: (value: string) => void;
  setError: (value: string) => void;
  setIsSending: (value: boolean) => void;
  setMessages: Dispatch<SetStateAction<ChatEntry[]>>;
};

function buildChatRequestBody(
  message: string,
  {
    attachedFiles,
    attachedFolders,
    attachedImages,
    options,
  }: {
  attachedFiles: string[];
  attachedFolders: string[];
  attachedImages: string[];
  options?: ChatSendOptions;
  },
): ChatRequestBody {
  const body: ChatRequestBody = { message };
  const attachments: ChatAttachment[] = [
    ...attachedFolders.map((path) => ({ type: "folder" as const, path })),
    ...attachedFiles.map((path) => ({ type: "file" as const, path })),
    ...attachedImages.map((path) => ({ type: "image" as const, path })),
  ];

  if (attachments.length > 0) {
    body.attachments = attachments;
  }
  if (options?.mcpServerIds && options.mcpServerIds.length > 0) {
    body.mcp_servers = options.mcpServerIds;
  }

  const selectedSkills = loadChatToolboxSelectedSkills();
  if (selectedSkills.length > 0) {
    body.skills = selectedSkills;
  }
  if (options?.continuousReasoningEnabled) {
    body.reasoning = { enabled: true };
  }

  return body;
}

export function useChatComposer({
  attachedFiles,
  attachedFolders,
  attachedImages,
  clearAttachments,
  restoreAttachments,
  draft,
  pendingRequestMessageRef,
  setDraft,
  setError,
  setIsSending,
  setMessages,
}: UseChatComposerArgs) {
  const handleSend = useCallback(
    async (options?: ChatSendOptions) => {
      const message = draft.trim();
      if (!message) {
        return;
      }

      const requestBody = buildChatRequestBody(message, {
        attachedFiles,
        attachedFolders,
        attachedImages,
        options,
      });
      const attachmentsSnapshot = {
        attachedFiles,
        attachedFolders,
        attachedImages,
      };
      const requestKey = createChatRequestKey();
      requestBody.request_key = requestKey;
      const userMessageId = `user-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

      setError("");
      setIsSending(true);
      pendingRequestMessageRef.current = { message, requestKey };
      setMessages((current) => [
        ...current,
        {
          id: userMessageId,
          role: "user",
          content: message,
          requestKey,
          retryRequestBody: requestBody,
        },
      ]);
      setDraft("");

      try {
        const submission = await chat(requestBody);
        clearAttachments();
        setMessages((current) =>
          ensureAssistantPlaceholder(current, submission.assistant_message_id, message, requestKey),
        );
      } catch (err) {
        const detail = err instanceof Error ? err.message : "发送失败";
        pendingRequestMessageRef.current = null;
        setError(detail);
        setDraft(message);
        restoreAttachments(attachmentsSnapshot);
        setMessages((current) =>
          current.map((entry) =>
            entry.id === userMessageId
              ? {
                  ...entry,
                  state: "failed",
                  errorMessage: detail,
                  retryRequestBody: requestBody,
                }
              : entry,
          ),
        );
      } finally {
        setIsSending(false);
      }
    },
    [
      attachedFiles,
      attachedFolders,
      attachedImages,
      clearAttachments,
      draft,
      pendingRequestMessageRef,
      restoreAttachments,
      setDraft,
      setError,
      setIsSending,
      setMessages,
    ],
  );

  const handleRetry = useCallback(
    async (message: ChatEntry) => {
      const requestBody = message.retryRequestBody ?? { message: message.content };
      const requestKey = message.requestKey ?? createChatRequestKey();
      requestBody.request_key = requestKey;

      setError("");
      setIsSending(true);
      pendingRequestMessageRef.current = { message: requestBody.message, requestKey };
      setMessages((current) =>
        current.map((entry) =>
          entry.id === message.id
            ? {
                ...entry,
                state: undefined,
                errorMessage: undefined,
                requestKey,
              }
            : entry,
        ),
      );

      try {
        const submission = await chat(requestBody);
        setMessages((current) =>
          ensureAssistantPlaceholder(current, submission.assistant_message_id, requestBody.message, requestKey),
        );
      } catch (err) {
        const detail = err instanceof Error ? err.message : "发送失败";
        pendingRequestMessageRef.current = null;
        setError(detail);
        setMessages((current) =>
          current.map((entry) =>
            entry.id === message.id
              ? {
                  ...entry,
                  state: "failed",
                  errorMessage: detail,
                  retryRequestBody: requestBody,
                }
              : entry,
          ),
        );
      } finally {
        setIsSending(false);
      }
    },
    [pendingRequestMessageRef, setError, setIsSending, setMessages],
  );

  const handleResume = useCallback(
    async (message: ChatEntry) => {
      const requestMessage = message.requestMessage?.trim();
      if (!requestMessage) {
        return;
      }

      setError("");
      setIsSending(true);
      pendingRequestMessageRef.current = {
        message: requestMessage,
        requestKey: message.requestKey ?? createChatRequestKey(),
      };
      setMessages((current) =>
        current.map((entry) =>
          entry.id === message.id
            ? {
                ...entry,
                state: "streaming",
                errorMessage: undefined,
              }
            : entry,
        ),
      );

      try {
        await resumeChat({
          message: requestMessage,
          assistant_message_id: message.id,
          partial_content: message.content,
          request_key: message.requestKey,
          reasoning_session_id: message.reasoningSessionId,
        });
      } catch (err) {
        const detail = err instanceof Error ? err.message : "续写失败";
        pendingRequestMessageRef.current = null;
        setError(detail);
        setMessages((current) =>
          current.map((entry) =>
            entry.id === message.id
              ? {
                  ...entry,
                  state: "failed",
                  errorMessage: detail,
                }
              : entry,
          ),
        );
      } finally {
        setIsSending(false);
      }
    },
    [pendingRequestMessageRef, setError, setIsSending, setMessages],
  );

  return { handleResume, handleRetry, handleSend };
}

function ensureAssistantPlaceholder(
  current: ChatEntry[],
  assistantMessageId: string | null | undefined,
  requestMessage: string,
  requestKey: string,
): ChatEntry[] {
  if (!assistantMessageId) {
    return current;
  }

  if (current.some((entry) => entry.id === assistantMessageId && entry.role === "assistant")) {
    return current;
  }

  return [
    ...current,
    {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      state: "streaming",
      requestKey,
      requestMessage,
    },
  ];
}
