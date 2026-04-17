const STRUCTURED_CONTENT_FENCE = "```";

export function normalizeMarkdownContent(content: string): string {
  const trimmed = content.trim();
  if (!trimmed) {
    return content;
  }

  if (hasExplicitMarkdown(trimmed) || trimmed.includes(STRUCTURED_CONTENT_FENCE)) {
    return content;
  }

  if (looksLikeJsonBlock(trimmed)) {
    return `${STRUCTURED_CONTENT_FENCE}json\n${trimmed}\n${STRUCTURED_CONTENT_FENCE}`;
  }

  if (looksLikeStructuredConfig(trimmed)) {
    return `${STRUCTURED_CONTENT_FENCE}text\n${trimmed}\n${STRUCTURED_CONTENT_FENCE}`;
  }

  return content;
}

function hasExplicitMarkdown(content: string): boolean {
  return /(^|\n)\s{0,3}(#{1,6}\s|[-*+]\s|\d+\.\s|>\s)/.test(content) || /\|.+\|/.test(content);
}

function looksLikeJsonBlock(content: string): boolean {
  if (!/^[\[{][\s\S]*[\]}]$/.test(content)) {
    return false;
  }

  try {
    const parsed = JSON.parse(content);
    return typeof parsed === "object" && parsed !== null;
  } catch {
    return false;
  }
}

function looksLikeStructuredConfig(content: string): boolean {
  const lines = content
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length < 3) {
    return false;
  }

  const structuredLineCount = lines.filter(
    (line) =>
      /^["'A-Za-z0-9_.\-/]+"\s*:/.test(line) ||
      /^[A-Za-z0-9_.\-/]+\s*[:=]\s*\S+/.test(line) ||
      /^[{}\[\],]+$/.test(line),
  ).length;

  return structuredLineCount / lines.length >= 0.7;
}
