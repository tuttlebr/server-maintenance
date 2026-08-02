function toDate(dt) {
  if (!dt) return null;
  const s = String(dt);
  const iso = s.endsWith("Z") || /[+-]\d\d:?\d\d$/.test(s) ? s : s + "Z";
  const ts = new Date(iso).getTime();
  return Number.isNaN(ts) ? null : ts;
}

export function relativeTime(dt) {
  const ts = toDate(dt);
  if (ts === null) return "";
  const seconds = Math.round((Date.now() - ts) / 1000);
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  const days = Math.round(seconds / 86400);
  if (days < 30) return `${days}d ago`;
  const months = Math.round(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.round(months / 12)}y ago`;
}

export function formatLongTime(dt) {
  const ts = toDate(dt);
  if (ts === null) return "";
  return new Date(ts).toLocaleString();
}

export function ageInMs(dt) {
  const ts = toDate(dt);
  if (ts === null) return null;
  return Date.now() - ts;
}
