import { afterEach, describe, expect, test } from "vitest";

import {
  CHAT_TOOLBOX_SELECTED_SKILLS_KEY,
  clearChatToolboxSelectedSkills,
  loadChatToolboxSelectedSkills,
  saveChatToolboxSelectedSkills,
} from "./chatToolboxPreferences";

afterEach(() => {
  window.localStorage.removeItem(CHAT_TOOLBOX_SELECTED_SKILLS_KEY);
});

describe("chatToolboxPreferences", () => {
  test("normalizes and persists selected skills", () => {
    saveChatToolboxSelectedSkills([" requirement-workflow ", "", "requirement-workflow", "bugfix-workflow"]);

    expect(loadChatToolboxSelectedSkills()).toEqual(["requirement-workflow", "bugfix-workflow"]);
  });

  test("returns empty list when persisted data is invalid", () => {
    window.localStorage.setItem(CHAT_TOOLBOX_SELECTED_SKILLS_KEY, "not-json");

    expect(loadChatToolboxSelectedSkills()).toEqual([]);
  });

  test("supports clearing persisted skills", () => {
    saveChatToolboxSelectedSkills(["requirement-workflow"]);
    clearChatToolboxSelectedSkills();

    expect(loadChatToolboxSelectedSkills()).toEqual([]);
  });
});
