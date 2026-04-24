import { renderHook, act } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

const { updatePersonaFeatures } = vi.hoisted(() => ({
  updatePersonaFeatures: vi.fn(),
}));

const { setAvatarWindowVisible } = vi.hoisted(() => ({
  setAvatarWindowVisible: vi.fn(),
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    updatePersonaFeatures,
  };
});

vi.mock("../avatar/avatarWindowController", () => ({
  setAvatarWindowVisible,
}));

import { useVrmAvatarFeature } from "./useVrmAvatarFeature";

test("updates persona avatar feature and syncs the VRM avatar window", async () => {
  const onError = vi.fn();
  const onPersonaChange = vi.fn();
  updatePersonaFeatures.mockResolvedValue({
    profile: { name: "小晏", features: { avatar_enabled: true } },
  });

  const { result } = renderHook(() =>
    useVrmAvatarFeature({
      onError,
      onPersonaChange,
    }),
  );

  await act(async () => {
    await result.current.handleAvatarEnabledChange(true);
  });

  expect(updatePersonaFeatures).toHaveBeenCalledWith({ avatar_enabled: true });
  expect(onPersonaChange).toHaveBeenCalledWith({ name: "小晏", features: { avatar_enabled: true } });
  expect(setAvatarWindowVisible).toHaveBeenCalledWith(true);
});

test("keeps the persona feature update when avatar window sync fails", async () => {
  const onError = vi.fn();
  const onPersonaChange = vi.fn();
  updatePersonaFeatures.mockResolvedValue({
    profile: { name: "小晏", features: { avatar_enabled: true } },
  });
  setAvatarWindowVisible.mockRejectedValue(new Error("window failed"));

  const { result } = renderHook(() =>
    useVrmAvatarFeature({
      onError,
      onPersonaChange,
    }),
  );

  await act(async () => {
    await result.current.handleAvatarEnabledChange(true);
  });

  expect(onPersonaChange).toHaveBeenCalledWith({ name: "小晏", features: { avatar_enabled: true } });
  expect(onError).toHaveBeenCalledWith("window failed");
});

beforeEach(() => {
  updatePersonaFeatures.mockReset();
  setAvatarWindowVisible.mockReset();
});
