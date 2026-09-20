export function accountPlacement(user, deviceId) {
  return user?.placements?.find(item => item.device_id === deviceId) || { device_id: deviceId, state: 'unverified', managed_sudo: null };
}
export function privilegeLabel(placement) {
  if (placement.state === 'absent') return 'Account absent';
  if (placement.state !== 'observed' || placement.managed_sudo == null) return 'Not verified';
  return placement.managed_sudo ? 'Managed grant present' : 'No managed grant';
}
export function exactPreviewTargets(job, devices, ids, now = Date.now()) {
  const names = devices.filter(d => ids.includes(d.id)).map(d => d.inventory_name).sort();
  const observed = Date.parse((job.finished_at || '').match(/Z$|[+-]\d\d:\d\d$/) ? job.finished_at : `${job.finished_at}Z`);
  return names.length > 0 && job.status === 'success' && job.playbook === 'package_preview.yml'
    && now - observed < 30 * 60 * 1000 && now >= observed
    && JSON.stringify(names) === JSON.stringify(String(job.target_devices || '').split(',').sort());
}
