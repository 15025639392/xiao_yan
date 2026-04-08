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
  timeoutSeconds?: number;
  allowedExecutables?: string[];
  allowedGitSubcommands?: string[];
};

export function isTauriRuntime(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as { __TAURI__?: unknown };
  return Boolean(w.__TAURI__);
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
      timeoutSeconds?: number;
      allowedExecutables?: string[];
      allowedGitSubcommands?: string[];
    } = { command };
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
