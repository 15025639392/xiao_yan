import { invoke } from "@tauri-apps/api/core";

import { isTauriRuntime, toTauriErrorMessage } from "./fsAccess";

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

function ensureTauriRuntime(): void {
  if (!isTauriRuntime()) {
    throw new Error("Tauri runtime not detected");
  }
}

export async function runCodexDelegate(request: CodexDelegateRequest): Promise<CodexDelegateResponse> {
  ensureTauriRuntime();
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
    throw new Error(toTauriErrorMessage(error));
  }
}
