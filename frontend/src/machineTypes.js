export const MACHINE_TYPES = {
  unknown: { label: "Unknown / Auto-detect", short: "Unknown", badge: "badge-outline", icon: "fas fa-question", hasGpu: false, hasFabricManager: false },
  dgx_spark: { label: "DGX Spark", short: "Spark", badge: "badge-outline", icon: "fas fa-bolt", hasGpu: true, hasFabricManager: false },
  dgx_workstation: { label: "DGX Workstation", short: "WS", badge: "badge-orange", icon: "fas fa-server", hasGpu: true, hasFabricManager: true },
  cpu_node: { label: "CPU Node", short: "CPU", badge: "badge-blue", icon: "fas fa-microchip", hasGpu: false, hasFabricManager: false },
  gpu_node: { label: "GPU Node", short: "GPU", badge: "badge-gray", icon: "fas fa-microchip", hasGpu: true, hasFabricManager: false },
};

const FALLBACK = MACHINE_TYPES.unknown;

export function getMachineType(type) {
  return MACHINE_TYPES[type] || FALLBACK;
}
