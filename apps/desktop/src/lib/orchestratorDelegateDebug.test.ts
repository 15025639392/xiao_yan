import { describe, expect, test } from "vitest";

import {
  buildDelegateDebugInfo,
  extractCodexStderrExcerpt,
  extractLastJsonlEvent,
} from "./orchestratorDelegateDebug";

describe("orchestratorDelegateDebug", () => {
  test("extracts the latest codex error block from stderr", () => {
    const stderr = [
      "2026-04-09T10:00:00.000Z WARN startup sync failed",
      "ERROR: {",
      '  "error": {',
      '    "message": "Invalid schema",',
      '    "code": "invalid_json_schema"',
      "  }",
      "}",
      "2026-04-09T10:00:01.000Z WARN thread/read failed",
    ].join("\n");

    expect(extractCodexStderrExcerpt(stderr)).toBe(
      ['ERROR: {', '  "error": {', '    "message": "Invalid schema",', '    "code": "invalid_json_schema"', "  }", "}"].join(
        "\n",
      ),
    );
  });

  test("extracts the last jsonl event from stdout", () => {
    const stdout = [
      '{"type":"thread.started","thread_id":"abc"}',
      '{"type":"turn.completed","usage":{"output_tokens":53}}',
    ].join("\n");

    expect(extractLastJsonlEvent(stdout)).toEqual({
      type: "turn.completed",
      usage: {
        output_tokens: 53,
      },
    });
  });

  test("builds delegate debug info only when there is useful content", () => {
    expect(buildDelegateDebugInfo("", "")).toBeUndefined();
    expect(
      buildDelegateDebugInfo(
        '{"type":"turn.completed"}',
        'ERROR: {\n  "error": {"message": "delegate failed"}\n}',
      ),
    ).toEqual({
      stderr_excerpt: 'ERROR: {\n  "error": {"message": "delegate failed"}\n}',
      last_jsonl_event: {
        type: "turn.completed",
      },
    });
  });
});
