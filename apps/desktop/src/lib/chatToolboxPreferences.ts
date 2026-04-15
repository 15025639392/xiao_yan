const CHAT_TOOLBOX_SELECTED_SKILLS_KEY = "chat.toolbox.selected_skills.v1";

function normalizeSkillNames(input: unknown): string[] {
  if (!Array.isArray(input)) {
    return [];
  }

  const seen = new Set<string>();
  const normalized: string[] = [];
  for (const item of input) {
    if (typeof item !== "string") {
      continue;
    }
    const trimmed = item.trim();
    if (!trimmed || seen.has(trimmed)) {
      continue;
    }
    seen.add(trimmed);
    normalized.push(trimmed);
  }

  return normalized;
}

export function loadChatToolboxSelectedSkills(): string[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(CHAT_TOOLBOX_SELECTED_SKILLS_KEY);
    if (!raw) {
      return [];
    }
    return normalizeSkillNames(JSON.parse(raw));
  } catch {
    return [];
  }
}

export function saveChatToolboxSelectedSkills(skillNames: string[]): void {
  if (typeof window === "undefined") {
    return;
  }

  const normalized = normalizeSkillNames(skillNames);
  window.localStorage.setItem(CHAT_TOOLBOX_SELECTED_SKILLS_KEY, JSON.stringify(normalized));
}

export function clearChatToolboxSelectedSkills(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(CHAT_TOOLBOX_SELECTED_SKILLS_KEY);
}

export { CHAT_TOOLBOX_SELECTED_SKILLS_KEY };
