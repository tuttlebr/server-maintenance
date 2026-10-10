export const CHECK = 'system.packages.preview';
export const INSTALL = 'system.update';
export const CLEANUP = 'containers.cleanup';
export const REBOOT = 'system.reboot';
export const ACTION_IDS = [CHECK, INSTALL, CLEANUP, REBOOT];
export const ACTIVE = ['pending', 'running', 'cancelling'];
export const namesFor = (job) => String(job?.target_devices || '').split(',').filter(Boolean);
export function sameTargets(job, devices) {
  const names = namesFor(job);
  return devices.length > 0 && names.length === devices.length && devices.every(d => names.includes(d.inventory_name));
}
export function validPackageCheck(job, devices, now = Date.now()) {
  if (job?.playbook !== 'package_preview.yml' || job.status !== 'success' || !sameTargets(job, devices)) return false;
  const raw = job.finished_at;
  const finished = Date.parse(raw && !/(Z|[+-]\d\d:\d\d)$/.test(raw) ? `${raw}Z` : raw);
  if (!Number.isFinite(finished) || now - finished >= 30 * 60_000 || finished > now + 60_000) return false;
  const reports = job.result_artifacts?.filter(r => r.report_type === 'packages') || [];
  return devices.every(d => reports.some(r => r.hostname === d.inventory_name && /^[a-f0-9]{64}$/.test(r.fingerprint)));
}
export function blockers(operation, selectedIds, devices) {
  return selectedIds.flatMap(id => {
    const device = devices.find(d => d.id === id);
    if (!device) return [{id, name: `Device #${id}`, reason: 'This device is no longer available.'}];
    if (operation?.eligible_device_ids.includes(id)) return [];
    return [{id, name: device.name, reason: operation?.excluded_devices?.find(d => d.id === id)?.reason || 'Not available for this action.'}];
  });
}
export function packageCount(job) {
  return (job?.result_artifacts || []).filter(r => r.report_type === 'packages').reduce((sum, r) => sum + (r.package_count ?? (r.changes || []).filter(line => line.startsWith('Inst ')).length), 0);
}
export const statusLabel = (status) => ({pending:'Queued', running:'Running', cancelling:'Stopping', success:'Completed', partial:'Partially completed', failed:'Failed', recovery_required:'Health check pending', unreachable:'Unreachable', not_checked:'Not reached', verification_failed:'Health check failed', cancelled:'Cancelled', not_started:'Not started'})[status] || status;

export const updateLabel = (count) => `${count} ${count === 1 ? "update" : "updates"}`;
export function packageRows(report) {
  return (Array.isArray(report.changes) ? report.changes : []).filter(line => line.startsWith('Inst ')).map(line => {
    const match = /^Inst (\S+)(?: \[([^\]]+)\])? \((\S+)/.exec(line);
    return match ? {name:match[1], current:match[2] || '', available:match[3]} : {name:line.slice(5),current:'',available:'See technical log'};
  });
}
