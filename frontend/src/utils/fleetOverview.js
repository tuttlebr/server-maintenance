import { hasCapability } from './devices.js';

export const ACTIVE_STATUSES = ['pending', 'running', 'cancelling'];
export const COMPLETED_STATUSES = ['success', 'partial', 'failed', 'recovery_required', 'cancelled'];
export const ATTENTION_GROUPS = [
  { id: 'recovery', label: 'Health check pending', title: 'Unfinished maintenance', severity: 'danger', action: 'Review affected devices', description: 'The next install or cleanup checks host health automatically before continuing.' },
  { id: 'offline', label: 'Offline', title: 'Investigate connectivity', severity: 'danger', action: 'Review connection state', description: 'Check device and connection evidence. Last seen is an observation time, not an outage duration.' },
  { id: 'storage', label: 'Root storage ≥85%', title: 'Inspect root storage pressure', severity: 'warning', operation: 'containers.cleanup', action: 'Review cache cleanup', description: 'Verify stale readings before planning cleanup. Cache cleanup removes unused container images and build cache.' },
  { id: 'verification', label: 'Needs verification', title: 'Refresh device evidence', severity: 'neutral', action: 'Review scan targets', description: 'Refresh stale or missing facts. Check overlapping work before starting another scan.' },
  { id: 'reboot', label: 'Reboot required', title: 'Plan required reboots', severity: 'warning', action: 'Review maintenance targets', description: 'Review workloads, prerequisites, and target eligibility before disruption.' },
];

export function diskPercent(device) {
  const value = device.disk_root_percent;
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100 ? value : null;
}
export function matchesAttention(device, reason) {
  switch (reason) {
    case 'recovery': return !!device.recovery_required;
    case 'offline': return device.status === 'offline';
    case 'storage': return diskPercent(device) !== null && diskPercent(device) >= 85;
    case 'verification': return !!device.facts_stale || !device.discovered_at || !['online', 'offline'].includes(device.status);
    case 'reboot': return !!device.reboot_required;
    default: return false;
  }
}
export function deviceConditions(device) {
  return ATTENTION_GROUPS.filter(group => matchesAttention(device, group.id)).map(group => ({
    ...group,
    label: group.id === 'storage' ? `Root storage ${diskPercent(device)}%` : group.id === 'verification' && !device.discovered_at ? 'No discovery recorded' : group.label,
  }));
}
export function attentionGroups(devices) {
  return ATTENTION_GROUPS.map(group => ({ ...group, devices: devices.filter(device => matchesAttention(device, group.id)).sort((a, b) =>
    (group.id === 'storage' ? diskPercent(b) - diskPercent(a) : 0) || a.name.localeCompare(b.name) || a.id - b.id
  ) })).filter(group => group.devices.length);
}
export function targetNames(job) {
  return String(job?.target_devices || '').split(',').map(name => name.trim()).filter(Boolean);
}
export function overlappingJobs(devices, jobs) {
  const names = new Set(devices.map(device => device.inventory_name).filter(Boolean));
  return jobs.filter(job => ACTIVE_STATUSES.includes(job.status) && targetNames(job).some(name => names.has(name)));
}
export function parseDeviceIds(value) {
  return [...new Set(String(value || '').split(',').filter(value => /^\d+$/.test(value)).map(Number).filter(id => Number.isSafeInteger(id) && id > 0))];
}
export function operationRoute(operation, devices, reason) {
  return { path: '/operations', query: { operation, devices: devices.map(device => device.id).join(','), ...(reason ? { reason } : {}) } };
}
export function groupRoute(group) {
  return group.operation ? operationRoute(group.operation, group.devices, group.id) : { path: '/devices', query: { reason: group.id } };
}
export function completedSummary(jobs) {
  const completed = jobs.filter(job => COMPLETED_STATUSES.includes(job.status));
  return { total: completed.length, counts: Object.fromEntries(COMPLETED_STATUSES.map(status => [status, completed.filter(job => job.status === status).length])) };
}
export function fleetCoverage(devices) {
  const reported = devices.filter(device => diskPercent(device) !== null);
  const robots = devices.filter(device => device.kind === 'robot');
  const gpu = devices.filter(device => device.kind !== 'robot' && hasCapability(device, 'gpu.inspect'));
  return { reported: reported.length, missing: devices.length - reported.length,
    stale: reported.filter(device => device.facts_stale || !device.discovered_at).length,
    worst: reported.length ? Math.max(...reported.map(diskPercent)) : null,
    robots: robots.length, gpu: gpu.length, other: devices.length - robots.length - gpu.length };
}
