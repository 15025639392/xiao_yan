import { describe, expect, test } from "vitest";
import type { ChatFolderPermission } from "./api";
import {
  addImportedProject,
  applyFolderPermissionsToRegistry,
  buildFolderPermissionPlan,
  createEmptyProjectRegistry,
  removeImportedProject,
  setActiveImportedProject,
  type ImportedProjectRegistry,
} from "./projects";

function sortByPath(permissions: ChatFolderPermission[]): ChatFolderPermission[] {
  return [...permissions].sort((a, b) => a.path.localeCompare(b.path));
}

describe("project registry", () => {
  test("adds imported project and marks it as active", () => {
    const initial = createEmptyProjectRegistry();

    const updated = addImportedProject(initial, "/Users/dev/project-a", "2026-04-08T08:00:00.000Z");

    expect(updated.active_project_path).toBe("/Users/dev/project-a");
    expect(updated.projects).toEqual([
      {
        path: "/Users/dev/project-a",
        name: "project-a",
        imported_at: "2026-04-08T08:00:00.000Z",
      },
    ]);
  });

  test("keeps imported_at when adding duplicate project", () => {
    const initial: ImportedProjectRegistry = {
      active_project_path: "/Users/dev/project-a",
      projects: [
        {
          path: "/Users/dev/project-a",
          name: "project-a",
          imported_at: "2026-04-08T08:00:00.000Z",
        },
      ],
    };

    const updated = addImportedProject(initial, "/Users/dev/project-a", "2026-04-08T09:00:00.000Z");

    expect(updated.projects).toHaveLength(1);
    expect(updated.projects[0]?.imported_at).toBe("2026-04-08T08:00:00.000Z");
    expect(updated.active_project_path).toBe("/Users/dev/project-a");
  });

  test("removes active project and falls back to next project", () => {
    const initial: ImportedProjectRegistry = {
      active_project_path: "/Users/dev/project-a",
      projects: [
        {
          path: "/Users/dev/project-a",
          name: "project-a",
          imported_at: "2026-04-08T08:00:00.000Z",
        },
        {
          path: "/Users/dev/project-b",
          name: "project-b",
          imported_at: "2026-04-08T08:10:00.000Z",
        },
      ],
    };

    const updated = removeImportedProject(initial, "/Users/dev/project-a");

    expect(updated.active_project_path).toBe("/Users/dev/project-b");
    expect(updated.projects.map((item) => item.path)).toEqual(["/Users/dev/project-b"]);
  });

  test("sets active project only when path exists", () => {
    const initial = addImportedProject(createEmptyProjectRegistry(), "/Users/dev/project-a", "2026-04-08T08:00:00.000Z");

    const unchanged = setActiveImportedProject(initial, "/Users/dev/project-missing");

    expect(unchanged).toEqual(initial);
  });

  test("builds permission plan with active project as full_access", () => {
    const initial: ImportedProjectRegistry = {
      active_project_path: "/Users/dev/project-b",
      projects: [
        {
          path: "/Users/dev/project-a",
          name: "project-a",
          imported_at: "2026-04-08T08:00:00.000Z",
        },
        {
          path: "/Users/dev/project-b",
          name: "project-b",
          imported_at: "2026-04-08T08:10:00.000Z",
        },
      ],
    };

    const plan = buildFolderPermissionPlan(initial);

    expect(sortByPath(plan)).toEqual([
      { path: "/Users/dev/project-a", access_level: "read_only" },
      { path: "/Users/dev/project-b", access_level: "full_access" },
    ]);
  });

  test("hydrates registry from folder permissions when local registry is empty", () => {
    const permissions: ChatFolderPermission[] = [
      { path: "/Users/dev/project-a", access_level: "full_access" },
      { path: "/Users/dev/project-b", access_level: "read_only" },
    ];

    const hydrated = applyFolderPermissionsToRegistry(createEmptyProjectRegistry(), permissions, "/Users/dev/project-b");

    expect(hydrated.projects.map((item) => item.path)).toEqual([
      "/Users/dev/project-a",
      "/Users/dev/project-b",
    ]);
    expect(hydrated.active_project_path).toBe("/Users/dev/project-b");
  });
});
