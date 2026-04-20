import { invoke } from "@tauri-apps/api/core";

export type AllowedDirResponse = {
  allowed_dir: string | null;
};

export type ShellRunResult = {
  stdout: string;
  stderr: string;
  exit_code: number;
  success: boolean;
  timed_out: boolean;
  truncated: boolean;
  duration_ms: number;
};

export type ShellRunOptions = {
  cwd?: string;
  timeoutSeconds?: number;
  allowedExecutables?: string[];
  allowedGitSubcommands?: string[];
};

export function isTauriRuntime(): boolean {
  if (typeof window === "undefined") return false;

  const w = window as unknown as {
    __TAURI__?: unknown;
    __TAURI_INTERNALS__?: unknown;
    __TAURI_IPC__?: unknown;
  };
  if (Boolean(w.__TAURI__) || Boolean(w.__TAURI_INTERNALS__) || typeof w.__TAURI_IPC__ === "function") {
    return true;
  }

  if (typeof navigator !== "undefined" && typeof navigator.userAgent === "string") {
    return /\btauri\b/i.test(navigator.userAgent);
  }

  return false;
}

function ensureTauri(): void {
  if (typeof window === "undefined") return;
  if (!isTauriRuntime()) {
    throw new Error("Tauri runtime not detected");
  }
}

export function toTauriErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  if (error && typeof error === "object" && "message" in error && typeof (error as any).message === "string") {
    return (error as any).message;
  }
  try {
    return JSON.stringify(error);
  } catch {
    return "unknown error";
  }
}

export async function fsSetAllowedDirectory(dirAbsPath: string): Promise<string> {
  ensureTauri();
  try {
    const res = await invoke<AllowedDirResponse>("fs_set_allowed_directory", { dir: dirAbsPath });
    if (!res.allowed_dir) throw new Error("failed to set allowed directory");
    return res.allowed_dir;
  } catch (e) {
    throw new Error(toTauriErrorMessage(e));
  }
}

export async function fsGetAllowedDirectory(): Promise<string | null> {
  ensureTauri();
  try {
    const res = await invoke<AllowedDirResponse>("fs_get_allowed_directory");
    return res.allowed_dir ?? null;
  } catch (e) {
    throw new Error(toTauriErrorMessage(e));
  }
}

export async function fsClearAllowedDirectory(): Promise<void> {
  ensureTauri();
  try {
    await invoke<AllowedDirResponse>("fs_clear_allowed_directory");
  } catch (e) {
    throw new Error(toTauriErrorMessage(e));
  }
}

export async function fsReadTextFile(relPath: string): Promise<string> {
  ensureTauri();
  try {
    return await invoke<string>("fs_read_text_file", { relPath });
  } catch (e) {
    throw new Error(toTauriErrorMessage(e));
  }
}

export async function fsWriteTextFile(relPath: string, content: string): Promise<void> {
  ensureTauri();
  try {
    await invoke<void>("fs_write_text_file", { relPath, content });
  } catch (e) {
    throw new Error(toTauriErrorMessage(e));
  }
}

export async function fsListDir(relPath: string): Promise<string[]> {
  ensureTauri();
  try {
    return await invoke<string[]>("fs_list_dir", { relPath });
  } catch (e) {
    throw new Error(toTauriErrorMessage(e));
  }
}

export async function shellRunCommand(command: string, options?: ShellRunOptions): Promise<ShellRunResult> {
  ensureTauri();
  try {
    const payload: {
      command: string;
      cwd?: string;
      timeoutSeconds?: number;
      allowedExecutables?: string[];
      allowedGitSubcommands?: string[];
    } = { command };
    if (typeof options?.cwd === "string" && options.cwd.trim()) {
      payload.cwd = options.cwd;
    }
    if (typeof options?.timeoutSeconds === "number" && Number.isFinite(options.timeoutSeconds)) {
      payload.timeoutSeconds = options.timeoutSeconds;
    }
    if (Array.isArray(options?.allowedExecutables) && options.allowedExecutables.length > 0) {
      payload.allowedExecutables = options.allowedExecutables;
    }
    if (Array.isArray(options?.allowedGitSubcommands) && options.allowedGitSubcommands.length > 0) {
      payload.allowedGitSubcommands = options.allowedGitSubcommands;
    }
    return await invoke<ShellRunResult>("shell_run", payload);
  } catch (e) {
    throw new Error(toTauriErrorMessage(e));
  }
}

// Browser capability wrappers

export type BrowserOpenOptions = {
  session_id?: string;
  headless?: boolean;
};

export type BrowserOpenResult = {
  session_id: string;
  url: string;
  resolved_url: string;
  title: string;
  status: string;
  opened_at: string;
};

export type BrowserSnapshotResult = {
  session_id: string;
  url: string;
  title: string;
  text_content: string;
  accessibility_tree: unknown;
  screenshot_path: string | null;
  captured_at: string;
};

export type BrowserExtractResult = {
  session_id: string;
  target: string;
  content: string;
  structured_data: unknown;
  source_url: string;
  captured_at: string;
};

export type BrowserCloseResult = {
  session_id: string;
  closed_at: string;
  status: string;
};

export async function browserOpen(url: string, options?: BrowserOpenOptions): Promise<BrowserOpenResult> {
  ensureTauri();
  try {
    return await invoke<BrowserOpenResult>("browser_open", { url, sessionId: options?.session_id, headless: options?.headless });
  } catch (e) {
    throw new Error(toTauriErrorMessage(e));
  }
}

export async function browserSnapshot(
  sessionId: string,
  options?: { include_text?: boolean; include_accessibility?: boolean; include_screenshot?: boolean; max_text_bytes?: number },
): Promise<BrowserSnapshotResult> {
  ensureTauri();
  try {
    return await invoke<BrowserSnapshotResult>("browser_snapshot", {
      session_id: sessionId,
      include_text: options?.include_text ?? true,
      include_accessibility: options?.include_accessibility ?? false,
      include_screenshot: options?.include_screenshot ?? false,
      max_text_bytes: options?.max_text_bytes,
    });
  } catch (e) {
    throw new Error(toTauriErrorMessage(e));
  }
}

export async function browserExtract(
  sessionId: string,
  target: string,
  options?: { schema?: Record<string, unknown>; max_items?: number },
): Promise<BrowserExtractResult> {
  ensureTauri();
  try {
    return await invoke<BrowserExtractResult>("browser_extract", {
      session_id: sessionId,
      target,
      schema: options?.schema,
      max_items: options?.max_items,
    });
  } catch (e) {
    throw new Error(toTauriErrorMessage(e));
  }
}

export async function browserClose(sessionId: string): Promise<BrowserCloseResult> {
  ensureTauri();
  try {
    return await invoke<BrowserCloseResult>("browser_close", { session_id: sessionId });
  } catch (e) {
    throw new Error(toTauriErrorMessage(e));
  }
}

export async function browserShutdown(): Promise<void> {
  ensureTauri();
  try {
    await invoke("browser_shutdown");
  } catch (e) {
    throw new Error(toTauriErrorMessage(e));
  }
}
