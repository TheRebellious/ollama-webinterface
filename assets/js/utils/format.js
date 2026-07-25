export function formatBytes(bytes) {
  if (bytes == null) return "--";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}
export const formatLargeBytes = formatBytes;
export function formatUptime(seconds) {
  if (seconds == null) return "--";
  const days = Math.floor(seconds / 86400), hours = Math.floor(seconds % 86400 / 3600), minutes = Math.floor(seconds % 3600 / 60);
  return days ? `${days}d ${hours}h` : hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}
export function getExtension(name) {
  const value = name.toLowerCase();
  if (value === "dockerfile" || value.endsWith(".dockerfile")) return "dockerfile";
  if (value === ".gitignore" || value.endsWith(".gitignore")) return "gitignore";
  return value.includes(".") ? value.split(".").pop() : "";
}
