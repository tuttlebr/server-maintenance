const HOSTNAME_COLLATOR = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: "base",
});

export function compareHostnames(a, b) {
  return HOSTNAME_COLLATOR.compare(String(a || ""), String(b || ""));
}

export function sortHostnames(hostnames) {
  return [...(hostnames || [])].sort(compareHostnames);
}

export function sortByHostname(items) {
  return [...(items || [])].sort((a, b) => compareHostnames(a?.hostname ?? a, b?.hostname ?? b));
}

export function formatHostList(value) {
  if (!value) return "";
  const text = String(value).trim();
  if (!text || text.toLowerCase() === "all") return text;

  const hosts = text
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean);

  return hosts.length > 1 ? sortHostnames(hosts).join(", ") : text;
}
