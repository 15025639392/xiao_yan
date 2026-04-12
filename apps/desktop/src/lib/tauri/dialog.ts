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

type FileDialogFilter = {
  name: string;
  extensions: string[];
};

export async function pickFiles(options?: {
  title?: string;
  filters?: FileDialogFilter[];
  multiple?: boolean;
}): Promise<string[]> {
  if (!isTauriRuntime()) return [];

  const selected = await open({
    directory: false,
    multiple: options?.multiple ?? true,
    title: options?.title ?? "选择文件",
    filters: options?.filters,
  });

  if (!selected) return [];
  if (Array.isArray(selected)) return selected.filter((item): item is string => typeof item === "string");
  return typeof selected === "string" ? [selected] : [];
}
