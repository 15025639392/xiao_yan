import { setAvatarWindowVisible } from "./avatarWindowController";
import { convertFileSrc } from "@tauri-apps/api/core";

const AVATAR_PREVIEW_MODEL_PATH_KEY = "xiaoyan.avatar.previewModelPath";

export function getStoredAvatarPreviewModelPath(): string | null {
  if (typeof window === "undefined") return null;
  const value = window.localStorage.getItem(AVATAR_PREVIEW_MODEL_PATH_KEY)?.trim();
  return value || null;
}

export async function getStoredAvatarPreviewModelUrl(): Promise<string | null> {
  const path = getStoredAvatarPreviewModelPath();
  if (!path) return null;
  return convertLocalPathToModelUrl(path);
}

export async function loadAvatarPreviewModel(path: string): Promise<void> {
  const normalized = path.trim();
  if (!normalized) {
    throw new Error("VRM 产物路径为空");
  }

  window.localStorage.setItem(AVATAR_PREVIEW_MODEL_PATH_KEY, normalized);
  window.dispatchEvent(new CustomEvent("xiaoyan:avatar-preview-model-changed", { detail: normalized }));
  await setAvatarWindowVisible(false);
  await setAvatarWindowVisible(true);
}

async function convertLocalPathToModelUrl(path: string): Promise<string> {
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("/avatar/")) {
    return path;
  }
  return convertFileSrc(path);
}
