export function lookupOrKey(map: Readonly<Record<string, string>>, key: string): string {
  return map[key] ?? key;
}

export function lookupOrDefault<T>(map: Readonly<Record<string, T>>, key: string, defaultValue: T): T {
  return map[key] ?? defaultValue;
}
