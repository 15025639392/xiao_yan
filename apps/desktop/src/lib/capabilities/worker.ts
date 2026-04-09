import { completeCapability, fetchPendingCapabilities, heartbeatCapabilityExecutor } from "./api";
import type { CapabilityRequest, CapabilityResult } from "./types";
import {
  fsGetAllowedDirectory,
  fsListDir,
  fsReadTextFile,
  fsWriteTextFile,
  isTauriRuntime,
  shellRunCommand,
} from "../tauri/fsAccess";

export type CapabilityWorkerOptions = {
  pollIntervalMs?: number;
  batchSize?: number;
  executorId?: string;
  logger?: Pick<Console, "warn" | "error">;
};

type EffectiveFilePolicy = {
  maxReadBytes: number;
  maxWriteBytes: number;
  maxSearchResults: number;
  maxListEntries: number;
  allowedSearchFilePatterns: string[];
};

const FALLBACK_FILE_POLICY: EffectiveFilePolicy = {
  maxReadBytes: 512 * 1024,
  maxWriteBytes: 512 * 1024,
  maxSearchResults: 200,
  maxListEntries: 500,
  allowedSearchFilePatterns: [
    "*.py",
    "*.ts",
    "*.tsx",
    "*.js",
    "*.jsx",
    "*.json",
    "*.md",
    "*.txt",
    "*.toml",
    "*.yaml",
    "*.yml",
    "*.rs",
    "*.go",
    "*.java",
    "*.c",
    "*.cpp",
    "*.h",
    "*.hpp",
    "*.css",
    "*.html",
  ],
};

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asPositiveInt(value: unknown, fallback: number, max: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  const rounded = Math.floor(value);
  if (rounded <= 0) return fallback;
  return Math.min(rounded, max);
}

function extractFilePolicy(args: Record<string, unknown>): EffectiveFilePolicy {
  const raw = args.file_policy;
  if (!raw || typeof raw !== "object") return FALLBACK_FILE_POLICY;
  const policy = raw as Record<string, unknown>;
  const patterns = Array.isArray(policy.allowed_search_file_patterns)
    ? policy.allowed_search_file_patterns.filter((item): item is string => typeof item === "string" && item.length > 0)
    : FALLBACK_FILE_POLICY.allowedSearchFilePatterns;
  return {
    maxReadBytes: asPositiveInt(policy.max_read_bytes, FALLBACK_FILE_POLICY.maxReadBytes, 2 * 1024 * 1024),
    maxWriteBytes: asPositiveInt(policy.max_write_bytes, FALLBACK_FILE_POLICY.maxWriteBytes, 2 * 1024 * 1024),
    maxSearchResults: asPositiveInt(policy.max_search_results, FALLBACK_FILE_POLICY.maxSearchResults, 500),
    maxListEntries: asPositiveInt(policy.max_list_entries, FALLBACK_FILE_POLICY.maxListEntries, 2000),
    allowedSearchFilePatterns: patterns.length > 0 ? patterns : FALLBACK_FILE_POLICY.allowedSearchFilePatterns,
  };
}

function truncateUtf8ByBytes(content: string, maxBytes: number): { content: string; truncated: boolean; sizeBytes: number } {
  const encoded = new TextEncoder().encode(content);
  if (encoded.length <= maxBytes) {
    return { content, truncated: false, sizeBytes: encoded.length };
  }
  const truncated = new TextDecoder().decode(encoded.slice(0, maxBytes));
  const truncatedSize = new TextEncoder().encode(truncated).length;
  return { content: truncated, truncated: true, sizeBytes: truncatedSize };
}

function isAbsolutePath(path: string): boolean {
  return path.startsWith("/") || /^[a-zA-Z]:[\\/]/.test(path) || path.startsWith("\\\\");
}

function toRelativePathForTauri(rawPath: string, allowedDir: string | null): { ok: true; path: string } | { ok: false; error: string } {
  const path = rawPath.trim();
  if (!path) {
    return { ok: false, error: "path is empty" };
  }

  if (!isAbsolutePath(path)) {
    return { ok: true, path };
  }

  if (!allowedDir) {
    return { ok: false, error: "no allowed directory set for absolute path" };
  }

  const normalizedAllowed = allowedDir.replace(/\\/g, "/").replace(/\/+$/, "");
  const normalizedPath = path.replace(/\\/g, "/");
  if (normalizedPath === normalizedAllowed) {
    return { ok: true, path: "." };
  }
  if (!normalizedPath.startsWith(`${normalizedAllowed}/`)) {
    return { ok: false, error: "absolute path is outside tauri allowed directory" };
  }
  return { ok: true, path: normalizedPath.slice(normalizedAllowed.length + 1) };
}

function globToRegExp(glob: string): RegExp {
  const escaped = glob.replace(/[.+^${}()|[\]\\]/g, "\\$&");
  const pattern = escaped.replace(/\*/g, ".*").replace(/\?/g, ".");
  return new RegExp(`^${pattern}$`);
}

function joinRelative(base: string, child: string): string {
  if (!base || base === ".") return child;
  return `${base.replace(/\/+$/, "")}/${child}`;
}

function getFileName(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  const idx = normalized.lastIndexOf("/");
  return idx >= 0 ? normalized.slice(idx + 1) : normalized;
}

async function searchInDirectory(
  relDir: string,
  query: string,
  fileMatcher: RegExp,
  maxResults: number,
  sink: Array<{ file: string; line: number; context: string }>,
): Promise<void> {
  if (sink.length >= maxResults) return;

  let names: string[] = [];
  try {
    names = await fsListDir(relDir);
  } catch {
    return;
  }

  for (const name of names) {
    if (sink.length >= maxResults) break;
    const child = joinRelative(relDir, name);
    const fileName = getFileName(child);

    if (fileMatcher.test(fileName)) {
      try {
        const content = await fsReadTextFile(child);
        const lines = content.split("\n");
        for (let i = 0; i < lines.length; i += 1) {
          if (lines[i].includes(query)) {
            sink.push({ file: child, line: i + 1, context: lines[i] });
            if (sink.length >= maxResults) break;
          }
        }
      } catch {
        // likely not a file; continue to directory probing
      }
    }

    if (sink.length >= maxResults) break;

    // Probe as directory recursively. If it's not a directory, fsListDir will fail quickly.
    await searchInDirectory(child, query, fileMatcher, maxResults, sink);
  }
}

function buildResult(
  request: CapabilityRequest,
  startedAt: Date,
  ok: boolean,
  output?: unknown,
  errorCode?: string,
  errorMessage?: string,
): CapabilityResult {
  const finishedAt = new Date();
  return {
    request_id: request.request_id,
    ok,
    output,
    error_code: errorCode,
    error_message: errorMessage,
    audit: {
      executor: "desktop",
      started_at: startedAt.toISOString(),
      finished_at: finishedAt.toISOString(),
      duration_ms: Math.max(0, finishedAt.getTime() - startedAt.getTime()),
    },
  };
}

export async function executeCapabilityLocally(request: CapabilityRequest): Promise<CapabilityResult> {
  const startedAt = new Date();
  const allowedDir = await fsGetAllowedDirectory().catch(() => null);
  const filePolicy = extractFilePolicy(request.args);

  try {
    if (request.capability === "fs.read") {
      const path = asString(request.args.path);
      if (!path) {
        return buildResult(request, startedAt, false, undefined, "invalid_args", "missing args.path");
      }
      const normalized = toRelativePathForTauri(path, allowedDir);
      if (!normalized.ok) {
        return buildResult(request, startedAt, false, undefined, "path_not_allowed", normalized.error);
      }
      const content = await fsReadTextFile(normalized.path);
      const requestedMaxBytes = asPositiveInt(request.args.max_bytes, filePolicy.maxReadBytes, 2 * 1024 * 1024);
      const maxBytes = Math.min(requestedMaxBytes, filePolicy.maxReadBytes);
      const limited = truncateUtf8ByBytes(content, maxBytes);
      return buildResult(request, startedAt, true, {
        path,
        content: limited.content,
        size_bytes: limited.sizeBytes,
        line_count: limited.content ? limited.content.split("\n").length : 1,
        truncated: limited.truncated,
      });
    }

    if (request.capability === "fs.list") {
      const path = asString(request.args.path) ?? ".";
      const normalized = toRelativePathForTauri(path, allowedDir);
      if (!normalized.ok) {
        return buildResult(request, startedAt, false, undefined, "path_not_allowed", normalized.error);
      }
      const entries = await fsListDir(normalized.path);
      const limitedEntries = entries.slice(0, filePolicy.maxListEntries);
      return buildResult(request, startedAt, true, {
        path,
        entries: limitedEntries,
        truncated: entries.length > limitedEntries.length,
      });
    }

    if (request.capability === "fs.write") {
      const path = asString(request.args.path);
      const content = asString(request.args.content);
      if (!path || content === null) {
        return buildResult(request, startedAt, false, undefined, "invalid_args", "missing args.path or args.content");
      }
      const normalized = toRelativePathForTauri(path, allowedDir);
      if (!normalized.ok) {
        return buildResult(request, startedAt, false, undefined, "path_not_allowed", normalized.error);
      }
      const contentBytes = new TextEncoder().encode(content).length;
      if (contentBytes > filePolicy.maxWriteBytes) {
        return buildResult(
          request,
          startedAt,
          false,
          undefined,
          "policy_violation",
          `content exceeds max_write_bytes (${filePolicy.maxWriteBytes})`,
        );
      }
      await fsWriteTextFile(normalized.path, content);
      return buildResult(request, startedAt, true, { path, bytes_written: contentBytes });
    }

    if (request.capability === "fs.search") {
      const query = asString(request.args.query);
      if (!query) {
        return buildResult(request, startedAt, false, undefined, "invalid_args", "missing args.query");
      }
      const searchPath = asString(request.args.search_path) ?? ".";
      const pattern = asString(request.args.file_pattern) ?? "*.py";
      const maxResultsRaw = request.args.max_results;
      const maxResults =
        typeof maxResultsRaw === "number" && Number.isFinite(maxResultsRaw)
          ? Math.max(1, Math.min(200, Math.floor(maxResultsRaw)))
          : 20;
      const limitedMaxResults = Math.min(maxResults, filePolicy.maxSearchResults);
      if (!filePolicy.allowedSearchFilePatterns.includes(pattern)) {
        return buildResult(
          request,
          startedAt,
          false,
          undefined,
          "policy_violation",
          `file pattern not allowed: ${pattern}`,
        );
      }

      const normalized = toRelativePathForTauri(searchPath, allowedDir);
      if (!normalized.ok) {
        return buildResult(request, startedAt, false, undefined, "path_not_allowed", normalized.error);
      }

      const matches: Array<{ file: string; line: number; context: string }> = [];
      const started = Date.now();
      await searchInDirectory(normalized.path, query, globToRegExp(pattern), limitedMaxResults, matches);
      const durationSeconds = Math.max(0, (Date.now() - started) / 1000);

      return buildResult(request, startedAt, true, {
        query,
        matches,
        total_matches: matches.length,
        search_duration_seconds: Number(durationSeconds.toFixed(3)),
      });
    }

    if (request.capability === "shell.run") {
      const command = asString(request.args.command);
      if (!command) {
        return buildResult(request, startedAt, false, undefined, "invalid_args", "missing args.command");
      }
      const timeoutRaw = request.args.timeout_seconds;
      const timeoutSeconds =
        typeof timeoutRaw === "number" && Number.isFinite(timeoutRaw)
          ? Math.max(1, Math.min(120, Math.floor(timeoutRaw)))
          : undefined;
      const cwd = asString(request.args.cwd) ?? undefined;
      const allowedExecutables = Array.isArray(request.args.allowed_executables)
        ? request.args.allowed_executables.filter((item): item is string => typeof item === "string" && item.length > 0)
        : undefined;
      const allowedGitSubcommands = Array.isArray(request.args.allowed_git_subcommands)
        ? request.args.allowed_git_subcommands.filter(
            (item): item is string => typeof item === "string" && item.length > 0,
          )
        : undefined;
      try {
        const result = await shellRunCommand(command, {
          cwd,
          timeoutSeconds,
          allowedExecutables,
          allowedGitSubcommands,
        });
        return buildResult(request, startedAt, true, result);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (message.startsWith("not_supported:")) {
          return buildResult(request, startedAt, false, undefined, "not_supported", message);
        }
        return buildResult(request, startedAt, false, undefined, "execution_error", message);
      }
    }

    return buildResult(
      request,
      startedAt,
      false,
      undefined,
      "not_supported",
      `capability not supported by desktop worker: ${request.capability}`,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return buildResult(request, startedAt, false, undefined, "execution_error", message);
  }
}

export function startCapabilityWorker(options: CapabilityWorkerOptions = {}): () => void {
  if (!isTauriRuntime()) {
    return () => {};
  }

  const pollIntervalMs = Math.max(300, options.pollIntervalMs ?? 500);
  const batchSize = Math.max(1, options.batchSize ?? 3);
  const executorId = options.executorId ?? "desktop";
  const logger = options.logger ?? console;

  let stopped = false;
  let inFlight = false;
  let timer: number | null = null;

  const tick = async () => {
    if (stopped || inFlight) {
      return;
    }
    inFlight = true;
    try {
      await heartbeatCapabilityExecutor(executorId);
      const pending = await fetchPendingCapabilities(executorId, batchSize);
      for (const item of pending.items) {
        const result = await executeCapabilityLocally(item.request);
        try {
          await completeCapability(result);
        } catch (error) {
          logger.warn("failed to complete capability request", error);
        }
      }
    } catch (error) {
      logger.warn("capability worker poll failed", error);
    } finally {
      inFlight = false;
    }
  };

  void tick();
  timer = window.setInterval(() => {
    void tick();
  }, pollIntervalMs);

  return () => {
    stopped = true;
    if (timer != null) {
      window.clearInterval(timer);
      timer = null;
    }
  };
}
