import { describe, expect, test, vi } from "vitest";

import type { CapabilityRequest } from "./types";

const testState = vi.hoisted(() => ({
  mockFetchPendingCapabilities: vi.fn(async () => ({ items: [] })),
  mockCompleteCapability: vi.fn(async () => ({ request_id: "req-1", status: "completed" })),
  mockHeartbeatCapabilityExecutor: vi.fn(async () => ({ executor: "desktop", heartbeat_at: new Date().toISOString() })),
  mockUpdateBrowserOrgan: vi.fn(async () => ({ ok: true })),
  mockUpdateBrowserSession: vi.fn(async () => ({ ok: true })),
  tauriRuntimeReady: true,
}));

vi.mock("./api", () => ({
  fetchPendingCapabilities: testState.mockFetchPendingCapabilities,
  completeCapability: testState.mockCompleteCapability,
  heartbeatCapabilityExecutor: testState.mockHeartbeatCapabilityExecutor,
}));

vi.mock("../api", async () => {
  const actual = await vi.importActual("../api");
  return {
    ...actual,
    updateBrowserOrgan: testState.mockUpdateBrowserOrgan,
    updateBrowserSession: testState.mockUpdateBrowserSession,
  };
});

vi.mock("../tauri/fsAccess", () => ({
  fsGetAllowedDirectory: vi.fn(async () => "/tmp/project"),
  fsReadTextFile: vi.fn(async (path: string) => {
    if (path === "notes.txt") return "hello";
    if (path === "docs.txt") return "hello world\nTODO: line";
    throw new Error("not a readable file");
  }),
  fsListDir: vi.fn(async (path: string) => {
    if (path === "." || path === "") return ["docs.txt"];
    throw new Error("not a directory");
  }),
  fsWriteTextFile: vi.fn(async () => undefined),
  shellRunCommand: vi.fn(async (command: string) => {
    if (command === "pwd") {
      return {
        stdout: "/tmp/project\n",
        stderr: "",
        exit_code: 0,
        success: true,
        timed_out: false,
        truncated: false,
        duration_ms: 5,
      };
    }
    throw new Error("not_supported: unsupported command");
  }),
  isTauriRuntime: vi.fn(() => testState.tauriRuntimeReady),
}));

import { executeCapabilityLocally, startCapabilityWorker } from "./worker";
import { shellRunCommand } from "../tauri/fsAccess";

function buildRequest(capability: CapabilityRequest["capability"], args: Record<string, unknown>): CapabilityRequest {
  return {
    request_id: "req-1",
    capability,
    args,
    risk_level: "safe",
    requires_approval: false,
    context: {},
  };
}

describe("capability worker local executor", () => {
  test("executes fs.read with tauri fs access", async () => {
    const result = await executeCapabilityLocally(buildRequest("fs.read", { path: "notes.txt" }));
    expect(result.ok).toBe(true);
    expect(result.output).toMatchObject({ path: "notes.txt", content: "hello" });
    expect(result.audit.executor).toBe("desktop");
  });

  test("executes shell.run through tauri shell bridge", async () => {
    const result = await executeCapabilityLocally(
      buildRequest("shell.run", {
        command: "pwd",
        allowed_executables: ["pwd", "git"],
        allowed_git_subcommands: ["status"],
      }),
    );
    expect(result.ok).toBe(true);
    expect(result.output).toMatchObject({
      success: true,
      exit_code: 0,
    });
    expect(shellRunCommand).toHaveBeenCalledWith(
      "pwd",
      expect.objectContaining({
        allowedExecutables: ["pwd", "git"],
        allowedGitSubcommands: ["status"],
      }),
    );
  });

  test("maps unsupported shell command to not_supported", async () => {
    const result = await executeCapabilityLocally(buildRequest("shell.run", { command: "curl example.com" }));
    expect(result.ok).toBe(false);
    expect(result.error_code).toBe("not_supported");
  });

  test("executes fs.search and returns structured matches", async () => {
    const result = await executeCapabilityLocally(
      buildRequest("fs.search", {
        query: "hello",
        search_path: ".",
        file_pattern: "*.txt",
        max_results: 10,
      }),
    );
    expect(result.ok).toBe(true);
    expect(result.output).toMatchObject({
      query: "hello",
      total_matches: expect.any(Number),
      matches: expect.any(Array),
    });
  });

  test("applies file policy max_read_bytes truncation", async () => {
    const result = await executeCapabilityLocally(
      buildRequest("fs.read", {
        path: "docs.txt",
        file_policy: {
          max_read_bytes: 5,
          max_write_bytes: 512000,
          max_search_results: 20,
          max_list_entries: 100,
          allowed_search_file_patterns: ["*.txt"],
        },
      }),
    );
    expect(result.ok).toBe(true);
    expect(result.output).toMatchObject({
      truncated: true,
    });
  });

  test("rejects fs.search when file pattern violates file policy", async () => {
    const result = await executeCapabilityLocally(
      buildRequest("fs.search", {
        query: "hello",
        search_path: ".",
        file_pattern: "*.txt",
        file_policy: {
          max_read_bytes: 512000,
          max_write_bytes: 512000,
          max_search_results: 20,
          max_list_entries: 100,
          allowed_search_file_patterns: ["*.py"],
        },
      }),
    );
    expect(result.ok).toBe(false);
    expect(result.error_code).toBe("policy_violation");
  });

  test("starts capability worker after tauri runtime becomes available later", async () => {
    vi.useFakeTimers();
    testState.tauriRuntimeReady = false;
    testState.mockHeartbeatCapabilityExecutor.mockClear();
    testState.mockFetchPendingCapabilities.mockClear();
    testState.mockUpdateBrowserOrgan.mockClear();

    const stop = startCapabilityWorker({ pollIntervalMs: 500 });

    await vi.advanceTimersByTimeAsync(1500);
    expect(testState.mockHeartbeatCapabilityExecutor).not.toHaveBeenCalled();

    testState.tauriRuntimeReady = true;
    await vi.advanceTimersByTimeAsync(1200);

    expect(testState.mockHeartbeatCapabilityExecutor).toHaveBeenCalledWith("desktop");
    expect(testState.mockFetchPendingCapabilities).toHaveBeenCalled();
    expect(testState.mockUpdateBrowserOrgan).toHaveBeenCalledWith(
      expect.objectContaining({
        binding_status: "bound",
        health_status: "healthy",
      }),
    );

    stop();
    testState.tauriRuntimeReady = true;
    vi.useRealTimers();
  });
});
