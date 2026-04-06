export function getParentPath(path: string): string {
  const parts = path.replace(/\/$/, "").split("/");
  parts.pop();
  return parts.join("/") || ".";
}

export function joinPath(basePath: string, childPath: string): string {
  if (basePath === ".") return childPath;
  return `${basePath}/${childPath}`;
}
