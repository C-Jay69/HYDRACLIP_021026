export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function timeAgo(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  const steps = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
    ["second", 1],
  ];
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size || unit === "second") {
      return formatter.format(Math.round(seconds / size), unit);
    }
  }
  return "just now";
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  const total = Math.max(0, Math.round(Number(seconds)));
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

export function formatLimit(value) {
  if (value === null || value === undefined) return "—";
  if (value === -1) return "Unlimited";
  return String(value);
}

export function parseFeatures(value) {
  try {
    const parsed = JSON.parse(value || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function statusLabel(status) {
  const labels = {
    queued: "Queued",
    generating: "Generating",
    completed: "Completed",
    failed: "Failed",
    cancelled: "Cancelled",
    running: "Running",
    pending: "Pending",
    published: "Published",
    manual_required: "Manual required",
  };
  return labels[status] || (status ? status.replace(/_/g, " ") : "Unknown");
}

export function platformLabel(platform) {
  const labels = {
    youtube: "YouTube",
    instagram: "Instagram",
    tiktok: "TikTok",
    x: "X",
  };
  return labels[platform] || platform || "Unknown";
}

export function toLocalDateTimeInput(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate(),
  )}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
