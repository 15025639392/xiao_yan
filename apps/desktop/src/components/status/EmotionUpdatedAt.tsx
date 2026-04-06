type EmotionUpdatedAtProps = {
  lastUpdated: string | null;
};

export function EmotionUpdatedAt({ lastUpdated }: EmotionUpdatedAtProps) {
  if (!lastUpdated) {
    return null;
  }

  return (
    <div style={{ marginTop: "var(--space-3)", fontSize: "0.75rem", color: "var(--text-tertiary)" }}>
      更新于: {new Date(lastUpdated).toLocaleString("zh-CN")}
    </div>
  );
}
