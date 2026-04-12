import { invoke } from "@tauri-apps/api/core";

import { toTauriErrorMessage } from "./fsAccess";

export type CodexDelegateCommandResult = {
  command: string;
  success: boolean;
  exit_code?: number | null;
  stdout?: string | null;
  stderr?: string | null;
  duration_ms?: number | null;
};

export type CodexDelegateRequest = {
  prompt: string;
  projectPath: string;
  runId: string;
  outputSchema: Record<string, unknown>;
  timeoutSeconds?: number;
};

export type CodexDelegateResponse = {
  status: "succeeded" | "failed" | string;
  summary: string;
  changed_files: string[];
  command_results: CodexDelegateCommandResult[];
  followup_needed: string[];
  error?: string | null;
  stdout: string;
  stderr: string;
  exit_code: number;
  success: boolean;
  timed_out: boolean;
};

export type CodexDelegateStopResponse = {
  run_id: string;
  status: "stopped" | "already_exited" | "not_found" | string;
  stopped: boolean;
  message: string;
};

function normalizeCodexDelegateInvokeError(raw: string): string {
  const message = raw.trim();
  if (!message) {
    return "调用 codex_run_delegate 失败：未返回可读错误（请重启客户端后重试）";
  }

  if (
    /(__TAURI__|__TAURI_INTERNALS__|__TAURI_IPC__)/i.test(message) ||
    /tauri runtime not detected/i.test(message) ||
    /failed to deserialize ipc|ipc channel/i.test(message) ||
    /invoke is not a function/i.test(message)
  ) {
    return `当前环境不是 Tauri 宿主，无法运行真实 Codex delegate (${message})`;
  }

  return message;
}

export async function runCodexDelegate(request: CodexDelegateRequest): Promise<CodexDelegateResponse> {
  try {
    return await invoke<CodexDelegateResponse>("codex_run_delegate", {
      request: {
        prompt: request.prompt,
        projectPath: request.projectPath,
        runId: request.runId,
        outputSchema: request.outputSchema,
        timeoutSeconds: request.timeoutSeconds,
      },
    });
  } catch (error) {
    throw new Error(normalizeCodexDelegateInvokeError(toTauriErrorMessage(error)));
  }
}

export async function stopCodexDelegate(runId: string, reason?: string): Promise<CodexDelegateStopResponse> {
  try {
    return await invoke<CodexDelegateStopResponse>("stop_codex_delegate", {
      request: {
        runId,
        reason,
      },
    });
  } catch (error) {
    throw new Error(normalizeCodexDelegateInvokeError(toTauriErrorMessage(error)));
  }
}
