import type { OrchestratorDelegateDebugInfo } from "./api";

const TIMESTAMP_PREFIX = /^\d{4}-\d{2}-\d{2}T/;

function truncateText(value: string, maxChars: number): string {
  if (value.length <= maxChars) {
    return value;
  }
  return `${value.slice(0, maxChars)}...`;
}

export function extractCodexStderrExcerpt(stderr: string, maxChars: number = 1200): string | null {
  const lines = stderr
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => line.trim().length > 0);

  if (lines.length === 0) {
    return null;
  }

  const errorIndex = [...lines].reverse().findIndex((line) => line.startsWith("ERROR:"));
  if (errorIndex >= 0) {
    const startIndex = lines.length - errorIndex - 1;
    const block: string[] = [lines[startIndex]];
    let braceBalance =
      (lines[startIndex].match(/{/g) ?? []).length -
      (lines[startIndex].match(/}/g) ?? []).length;
    for (let index = startIndex + 1; index < lines.length; index += 1) {
      const line = lines[index];
      if (TIMESTAMP_PREFIX.test(line)) {
        break;
      }
      block.push(line);
      braceBalance += (line.match(/{/g) ?? []).length - (line.match(/}/g) ?? []).length;
      if (braceBalance <= 0) {
        break;
      }
    }
    return truncateText(block.join("\n"), maxChars);
  }

  const fallbackLine =
    [...lines].reverse().find((line) => /error|failed|invalid/i.test(line)) ??
    lines[lines.length - 1];
  return truncateText(fallbackLine, Math.min(maxChars, 400));
}

export function extractLastJsonlEvent(stdout: string): Record<string, unknown> | null {
  const lines = stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const candidate = lines[index];
    try {
      const parsed = JSON.parse(candidate) as unknown;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      continue;
    }
  }

  return null;
}

export function buildDelegateDebugInfo(stdout: string, stderr: string): OrchestratorDelegateDebugInfo | undefined {
  const stderrExcerpt = extractCodexStderrExcerpt(stderr);
  const lastJsonlEvent = extractLastJsonlEvent(stdout);

  if (!stderrExcerpt && !lastJsonlEvent) {
    return undefined;
  }

  return {
    stderr_excerpt: stderrExcerpt,
    last_jsonl_event: lastJsonlEvent,
  };
}
