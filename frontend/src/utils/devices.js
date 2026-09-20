export const DEVICE_KINDS = {
  generic: { label: "Generic device", short: "Generic", icon: "fa-cube", badge: "badge-outline" },
  server: { label: "Server", short: "Server", icon: "fa-server", badge: "badge-blue" },
  workstation: { label: "Workstation", short: "Workstation", icon: "fa-desktop", badge: "badge-purple" },
  edge: { label: "Edge device", short: "Edge", icon: "fa-microchip", badge: "badge-orange" },
  robot: { label: "Robot", short: "Robot", icon: "fa-robot", badge: "badge-teal" },
};

export function deviceKind(kind) { return DEVICE_KINDS[kind] || DEVICE_KINDS.generic; }
export function hasCapability(device, capability) { return (device?.capabilities || []).includes(capability); }
export function devicePlatformName(device) {
  const dgx = device?.facts?.dgx;
  if (!dgx || typeof dgx !== "object") return "";
  return [dgx.pretty_name, dgx.name]
    .find((value) => typeof value === "string" && value.trim())
    ?.trim() || "";
}
export function deviceMatchesSearch(device, query) {
  const term = String(query || "").trim().toLowerCase();
  if (!term) return true;
  const dgx = device?.facts?.dgx || {};
  const searchable = [
    device?.name,
    device?.vendor,
    device?.model,
    device?.endpoint,
    dgx.pretty_name,
    dgx.name,
    dgx.platform,
  ].map((value) => String(value || "").toLowerCase()).join(" ");
  return searchable.includes(term);
}
export function formatTargetList(value) {
  if (!value) return "No devices recorded";
  const items = String(value).split(",").map((item) => item.trim()).filter(Boolean);
  if (items.length <= 2) return items.join(", ");
  return `${items.slice(0, 2).join(", ")} +${items.length - 2}`;
}

const OPERATION_LABELS = {
  "host_facts.yml": "Scan device",
  "maintenance_assessment.yml": "Assess maintenance readiness",
  "storage_analysis.yml": "Analyze storage",
  "gpu_usage.yml": "Inspect GPU usage",
  "reboot.yml": "Reboot",
  "system_update.yml": "Update system packages",
  "host_bootstrap.yml": "Bootstrap device",
  "docker_cleanup.yml": "Clean container cache",
  "driver_upgrade.yml": "Update NVIDIA drivers",
  "fabric_manager.yml": "Check Fabric Manager",
  "mig_management.yml": "Check MIG mode",
  "host_drain.yml": "Check Kubernetes readiness",
  "firmware_inventory.yml": "Inspect firmware",
  "firmware_update.yml": "Update firmware",
  "reachy.health": "Check Reachy health",
  "reachy.logs.read": "Collect Reachy logs",
  "reachy.daemon.restart": "Restart Reachy daemon",
  "reachy.software.update": "Update Reachy software",
  "reachy_app_reset.yml": "Reset Reachy apps",
};
export function operationLabel(value) { return OPERATION_LABELS[value] || String(value || "Operation").replace(/\.yml$/, "").replaceAll("_", " "); }
