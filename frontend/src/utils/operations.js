// An empty selection must never widen an operation to the whole fleet.
export function selectedOperationTargets(operation, selectedIds) {
  const eligible = new Set(operation.eligible_device_ids);
  return [...new Set(selectedIds)].filter((id) => eligible.has(id));
}

const OPERATION_HINTS = {
  "containers.cleanup": "unused images, cache, and networks",
  "firmware.inspect": "devices and available updates",
  "firmware.update": "apply updates; may need a reboot",
  "gpu.inspect": "utilization, memory, and processes",
  "kubernetes.drain": "workloads and scheduling status",
  "kubernetes.drain.execute": "cordon and evict workloads",
  "kubernetes.resume": "allow scheduling after health checks",
  "nvidia.driver.manage": "installed driver branch; may reboot",
  "nvidia.fabric_manager.manage": "NVLink and NVSwitch services",
  "nvidia.mig.manage": "Multi-Instance GPU",
  "reachy.apps.reset": "delete installed app environment",
  "reachy.daemon.restart": "restart robot software",
  "reachy.health": "connectivity and robot state",
  "reachy.logs.read": "recent daemon logs",
  "reachy.recover": "remote job and daemon health",
  "reachy.software.update": "latest stable robot software",
  "services.inspect": "service names and current state",
  "services.manage": "start, stop, or restart a service",
  "storage.inspect": "/home capacity and configured fstab mounts",
  "system.assess": "maintenance blockers and warnings",
  "system.bootstrap": "sudo and container setup",
  "system.packages.preview": "review changes before installing",
  "system.reboot": "restart selected devices",
  "system.recover": "health checks after interrupted maintenance",
  "system.scan": "refresh hardware and health facts",
  "system.update": "apply a reviewed package preview",
};

export function operationOptionLabel(operation) {
  const hint = OPERATION_HINTS[operation.id] || operation.category;
  return hint ? `${operation.label} (${hint})` : operation.label;
}

export function sortOperationsByLabel(operations) {
  return [...operations].sort((a, b) => a.label.localeCompare(b.label, "en", { sensitivity: "base", numeric: true }));
}
