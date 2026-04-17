import { useCallback, useState } from "react";

import { upsertChatFolderPermission } from "../../lib/api";
import { normalizeProjectPath } from "../../lib/projects";
import { isTauriRuntime, pickDirectory, pickFiles } from "../../lib/tauri";

type UseChatAttachmentsArgs = {
  onError: (message: string) => void;
};

type UseChatAttachmentsResult = {
  attachedFiles: string[];
  attachedFolders: string[];
  attachedImages: string[];
  handlePickChatFiles: () => Promise<void>;
  handlePickChatFolder: () => Promise<void>;
  handlePickChatImages: () => Promise<void>;
  handleRemoveAttachedFile: (path: string) => void;
  handleRemoveAttachedFolder: (path: string) => void;
  handleRemoveAttachedImage: (path: string) => void;
  setAttachedFiles: React.Dispatch<React.SetStateAction<string[]>>;
  setAttachedFolders: React.Dispatch<React.SetStateAction<string[]>>;
  setAttachedImages: React.Dispatch<React.SetStateAction<string[]>>;
};

export function useChatAttachments({ onError }: UseChatAttachmentsArgs): UseChatAttachmentsResult {
  const [attachedFolders, setAttachedFolders] = useState<string[]>([]);
  const [attachedFiles, setAttachedFiles] = useState<string[]>([]);
  const [attachedImages, setAttachedImages] = useState<string[]>([]);

  const handlePickChatFolder = useCallback(async () => {
    if (!isTauriRuntime()) {
      onError("当前环境不是 Tauri 宿主，无法选择文件夹。");
      return;
    }

    onError("");
    try {
      const selected = await pickDirectory();
      if (!selected) {
        return;
      }

      const normalizedPath = normalizeProjectPath(selected);
      await upsertChatFolderPermission(normalizedPath, "read_only");
      setAttachedFolders((current) => (current.includes(normalizedPath) ? current : [...current, normalizedPath]));
    } catch (error) {
      onError(error instanceof Error ? error.message : "添加文件夹失败");
    }
  }, [onError]);

  const handlePickChatFiles = useCallback(async () => {
    if (!isTauriRuntime()) {
      onError("当前环境不是 Tauri 宿主，无法选择文件。");
      return;
    }

    onError("");
    try {
      const selected = await pickFiles({
        title: "选择附件文件",
        filters: [
          {
            name: "文档与代码",
            extensions: ["txt", "md", "markdown", "json", "yaml", "yml", "toml", "csv", "log", "pdf", "py", "ts", "tsx", "js", "jsx"],
          },
        ],
        multiple: true,
      });
      if (selected.length === 0) {
        return;
      }

      const normalized = normalizeAttachedPaths(selected);
      await grantParentFolderPermissions(normalized);
      setAttachedFiles((current) => mergeUniquePaths(current, normalized));
    } catch (error) {
      onError(error instanceof Error ? error.message : "添加文件失败");
    }
  }, [onError]);

  const handlePickChatImages = useCallback(async () => {
    if (!isTauriRuntime()) {
      onError("当前环境不是 Tauri 宿主，无法选择图片。");
      return;
    }

    onError("");
    try {
      const selected = await pickFiles({
        title: "选择图片附件",
        filters: [
          {
            name: "图片",
            extensions: ["png", "jpg", "jpeg", "webp", "gif"],
          },
        ],
        multiple: true,
      });
      if (selected.length === 0) {
        return;
      }

      const normalized = normalizeAttachedPaths(selected);
      await grantParentFolderPermissions(normalized);
      setAttachedImages((current) => mergeUniquePaths(current, normalized));
    } catch (error) {
      onError(error instanceof Error ? error.message : "添加图片失败");
    }
  }, [onError]);

  const handleRemoveAttachedFolder = useCallback((path: string) => {
    setAttachedFolders((current) => current.filter((item) => item !== path));
  }, []);

  const handleRemoveAttachedFile = useCallback((path: string) => {
    setAttachedFiles((current) => current.filter((item) => item !== path));
  }, []);

  const handleRemoveAttachedImage = useCallback((path: string) => {
    setAttachedImages((current) => current.filter((item) => item !== path));
  }, []);

  return {
    attachedFiles,
    attachedFolders,
    attachedImages,
    handlePickChatFiles,
    handlePickChatFolder,
    handlePickChatImages,
    handleRemoveAttachedFile,
    handleRemoveAttachedFolder,
    handleRemoveAttachedImage,
    setAttachedFiles,
    setAttachedFolders,
    setAttachedImages,
  };
}

async function grantParentFolderPermissions(paths: string[]): Promise<void> {
  const parentFolders = new Set(
    paths
      .map((path) => resolveParentDirectory(path))
      .filter((path): path is string => Boolean(path)),
  );
  for (const folderPath of parentFolders) {
    await upsertChatFolderPermission(folderPath, "read_only");
  }
}

function normalizeAttachedPaths(paths: string[]): string[] {
  const normalized: string[] = [];
  for (const path of paths) {
    const trimmed = path.trim();
    if (!trimmed) {
      continue;
    }
    const normalizedPath = normalizeProjectPath(trimmed);
    if (!normalized.includes(normalizedPath)) {
      normalized.push(normalizedPath);
    }
  }
  return normalized;
}

function mergeUniquePaths(current: string[], incoming: string[]): string[] {
  const merged = [...current];
  for (const path of incoming) {
    if (!merged.includes(path)) {
      merged.push(path);
    }
  }
  return merged;
}

function resolveParentDirectory(path: string): string | null {
  const normalized = normalizeProjectPath(path);
  const slashIndex = Math.max(normalized.lastIndexOf("/"), normalized.lastIndexOf("\\"));
  if (slashIndex <= 0) {
    return null;
  }
  const parent = normalized.slice(0, slashIndex);
  return parent ? normalizeProjectPath(parent) : null;
}
