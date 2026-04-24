import { beforeEach, expect, test, vi } from "vitest";

import { getStoredAvatarPreviewModelPath, loadAvatarPreviewModel } from "./avatarPreviewModel";

const { setAvatarWindowVisible } = vi.hoisted(() => ({
  setAvatarWindowVisible: vi.fn(),
}));

vi.mock("./avatarWindowController", () => ({
  setAvatarWindowVisible,
}));

beforeEach(() => {
  localStorage.clear();
  setAvatarWindowVisible.mockReset();
});

test("stores preview model path and reopens avatar window without changing persona", async () => {
  await loadAvatarPreviewModel("/tmp/generated.vrm");

  expect(getStoredAvatarPreviewModelPath()).toBe("/tmp/generated.vrm");
  expect(setAvatarWindowVisible).toHaveBeenCalledWith(false);
  expect(setAvatarWindowVisible).toHaveBeenCalledWith(true);
});
