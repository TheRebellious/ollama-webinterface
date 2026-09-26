/**
 * Format raw byte count into human-readable unit string (B, KB, MB, GB).
 *
 * @param {number|null|undefined} bytes - Number of bytes.
 * @returns {string} Formatted string, e.g. "12.4 MB", or "--" if null.
 */
export function formatBytes(bytes) {
  if (bytes == null) return "--";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}

export const formatLargeBytes = formatBytes;

/**
 * Format uptime duration in seconds to days, hours, and minutes.
 *
 * @param {number|null|undefined} seconds - Uptime in seconds.
 * @returns {string} Formatted uptime string, e.g. "2d 4h" or "45m".
 */
export function formatUptime(seconds) {
  if (seconds == null) return "--";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return days ? `${days}d ${hours}h` : hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

/**
 * Extract normalized lowercase file extension from a filename or path.
 *
 * @param {string} name - File name or path.
 * @returns {string} Extension without leading dot (e.g. "docx", "json", "dockerfile").
 */
export function getExtension(name) {
  const value = String(name || "").toLowerCase();
  if (value === "dockerfile" || value.endsWith(".dockerfile")) return "dockerfile";
  if (value === ".gitignore" || value.endsWith(".gitignore")) return "gitignore";
  return value.includes(".") ? value.split(".").pop() : "";
}
