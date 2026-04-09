import type { ChatFolderPermission } from "./api";

export type ImportedProject = {
  path: string;
  name: string;
  imported_at: string;
};

export type ImportedProjectRegistry = {
  projects: ImportedProject[];
  active_project_path: string | null;
};

export const IMPORTED_PROJECTS_STORAGE_KEY = "desktop.imported-projects.v1";

function getDefaultStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage;
}

export function normalizeProjectPath(rawPath: string): string {
  const trimmed = rawPath.trim();
  if (!trimmed) {
    return "";
  }

  const normalized = trimmed.replace(/\\/g, "/");
  if (normalized === "/") {
    return normalized;
  }
  if (/^[a-zA-Z]:\/$/.test(normalized)) {
    return normalized;
  }

  return normalized.replace(/\/+$/, "");
}

export function getProjectNameFromPath(path: string): string {
  const normalized = normalizeProjectPath(path);
  if (!normalized) {
    return "未命名项目";
  }

  const parts = normalized.split("/").filter(Boolean);
  if (parts.length === 0) {
    return normalized;
  }

  return parts[parts.length - 1] ?? normalized;
}

export function createEmptyProjectRegistry(): ImportedProjectRegistry {
  return {
    projects: [],
    active_project_path: null,
  };
}

export function addImportedProject(
  registry: ImportedProjectRegistry,
  rawPath: string,
  importedAt: string = new Date().toISOString(),
): ImportedProjectRegistry {
  const normalizedPath = normalizeProjectPath(rawPath);
  if (!normalizedPath) {
    return registry;
  }

  const existing = registry.projects.find((item) => normalizeProjectPath(item.path) === normalizedPath);
  const nextProject: ImportedProject = {
    path: normalizedPath,
    name: getProjectNameFromPath(normalizedPath),
    imported_at: existing?.imported_at ?? importedAt,
  };

  const withoutExisting = registry.projects.filter((item) => normalizeProjectPath(item.path) !== normalizedPath);

  return {
    projects: [...withoutExisting, nextProject],
    active_project_path: normalizedPath,
  };
}

export function removeImportedProject(registry: ImportedProjectRegistry, rawPath: string): ImportedProjectRegistry {
  const normalizedPath = normalizeProjectPath(rawPath);
  const nextProjects = registry.projects.filter((item) => normalizeProjectPath(item.path) !== normalizedPath);

  if (nextProjects.length === registry.projects.length) {
    return registry;
  }

  const normalizedActivePath = registry.active_project_path ? normalizeProjectPath(registry.active_project_path) : null;
  const nextActivePath =
    normalizedActivePath === normalizedPath
      ? (nextProjects[0]?.path ?? null)
      : normalizedActivePath && nextProjects.some((item) => normalizeProjectPath(item.path) === normalizedActivePath)
        ? normalizedActivePath
        : (nextProjects[0]?.path ?? null);

  return {
    projects: nextProjects,
    active_project_path: nextActivePath,
  };
}

export function setActiveImportedProject(registry: ImportedProjectRegistry, rawPath: string): ImportedProjectRegistry {
  const normalizedPath = normalizeProjectPath(rawPath);
  const exists = registry.projects.some((item) => normalizeProjectPath(item.path) === normalizedPath);
  if (!exists) {
    return registry;
  }

  return {
    ...registry,
    active_project_path: normalizedPath,
  };
}

export function buildFolderPermissionPlan(registry: ImportedProjectRegistry): ChatFolderPermission[] {
  const activePath = registry.active_project_path ? normalizeProjectPath(registry.active_project_path) : null;

  return registry.projects.map((project) => {
    const normalizedPath = normalizeProjectPath(project.path);
    return {
      path: normalizedPath,
      access_level: normalizedPath === activePath ? "full_access" : "read_only",
    };
  });
}

export function applyFolderPermissionsToRegistry(
  registry: ImportedProjectRegistry,
  permissions: ChatFolderPermission[],
  preferredActivePath: string | null = null,
): ImportedProjectRegistry {
  const mergedProjects: ImportedProject[] = [];
  const seen = new Set<string>();

  for (const project of registry.projects) {
    const normalized = normalizeProjectPath(project.path);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    mergedProjects.push({
      ...project,
      path: normalized,
      name: project.name || getProjectNameFromPath(normalized),
    });
    seen.add(normalized);
  }

  for (const permission of permissions) {
    const normalized = normalizeProjectPath(permission.path);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    mergedProjects.push({
      path: normalized,
      name: getProjectNameFromPath(normalized),
      imported_at: new Date(0).toISOString(),
    });
    seen.add(normalized);
  }

  const activeCandidates = [
    preferredActivePath,
    registry.active_project_path,
    permissions.find((item) => item.access_level === "full_access")?.path ?? null,
    mergedProjects[0]?.path ?? null,
  ];

  let activeProjectPath: string | null = null;
  for (const candidate of activeCandidates) {
    const normalized = candidate ? normalizeProjectPath(candidate) : "";
    if (!normalized) {
      continue;
    }
    if (mergedProjects.some((item) => normalizeProjectPath(item.path) === normalized)) {
      activeProjectPath = normalized;
      break;
    }
  }

  return {
    projects: mergedProjects,
    active_project_path: activeProjectPath,
  };
}

function isImportedProject(value: unknown): value is ImportedProject {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.path === "string" &&
    typeof candidate.name === "string" &&
    typeof candidate.imported_at === "string"
  );
}

export function loadImportedProjectRegistry(storage: Storage | null = getDefaultStorage()): ImportedProjectRegistry {
  if (!storage) {
    return createEmptyProjectRegistry();
  }

  try {
    const raw = storage.getItem(IMPORTED_PROJECTS_STORAGE_KEY);
    if (!raw) {
      return createEmptyProjectRegistry();
    }

    const parsed = JSON.parse(raw) as Partial<ImportedProjectRegistry>;
    const projects = Array.isArray(parsed.projects) ? parsed.projects.filter(isImportedProject) : [];
    const active_project_path = typeof parsed.active_project_path === "string" ? parsed.active_project_path : null;

    return applyFolderPermissionsToRegistry(
      {
        projects,
        active_project_path,
      },
      [],
      active_project_path,
    );
  } catch {
    return createEmptyProjectRegistry();
  }
}

export function saveImportedProjectRegistry(
  registry: ImportedProjectRegistry,
  storage: Storage | null = getDefaultStorage(),
): void {
  if (!storage) {
    return;
  }

  storage.setItem(IMPORTED_PROJECTS_STORAGE_KEY, JSON.stringify(registry));
}
