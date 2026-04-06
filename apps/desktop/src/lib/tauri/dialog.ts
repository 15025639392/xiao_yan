import { open } from "@tauri-apps/plugin-dialog";
import { isTauriRuntime } from "./fsAccess";

export async function pickDirectory(): Promise<string | null> {
  if (!isTauriRuntime()) return null;

  const selected = await open({
    directory: true,
    multiple: false,
    title: "选择允许访问的文件夹",
  });

  if (!selected) return null;
  if (Array.isArray(selected)) return selected[0] ?? null;
  return selected;
}

