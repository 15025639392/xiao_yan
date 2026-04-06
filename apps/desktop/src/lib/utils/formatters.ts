export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const unit = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const index = Math.floor(Math.log(bytes) / Math.log(unit));
  return parseFloat((bytes / Math.pow(unit, index)).toFixed(1)) + " " + sizes[index];
}

export function formatDateTimeZh(dateLike: string | Date): string {
  const date = dateLike instanceof Date ? dateLike : new Date(dateLike);
  return date.toLocaleString("zh-CN");
}
