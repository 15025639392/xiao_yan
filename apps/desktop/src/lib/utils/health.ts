export function getHealthColor(score: number): string {
  if (score >= 80) return "var(--success)";
  if (score >= 60) return "var(--info)";
  if (score >= 40) return "var(--warning)";
  return "var(--danger)";
}
