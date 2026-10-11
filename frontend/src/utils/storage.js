const virtualTypes = new Set(['proc','sysfs','securityfs','debugfs','tracefs','cgroup','cgroup2','devpts','devtmpfs','pstore','efivarfs','configfs','fusectl','mqueue','hugetlbfs','binfmt_misc','bpf','rpc_pipefs']);
const networkTypes = new Set(['nfs','nfs4','cifs','smb','smb2','smb3','ceph','glusterfs','lustre','fuse.sshfs']);
export const hasNumber = value => typeof value === 'number' && Number.isFinite(value);
export function storageSize(value) {
  if (!hasNumber(value)) return 'Unavailable';
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} TiB`;
  return value >= 1024 ? `${(value / 1024).toFixed(1)} GiB` : `${value.toLocaleString()} MiB`;
}
export const virtualMount = mount => virtualTypes.has(mount.fstype || mount.configured_fstype);
export function storageState(mount) {
  if (mount.accessible) return 'Mounted';
  if (virtualMount(mount) && mount.mounted) return 'Virtual filesystem';
  if (mount.status === 'automount_pending') return 'On demand';
  if (mount.status === 'unmounted') return 'Not mounted';
  return 'Usage unavailable';
}
export function storageIssue(mount) {
  if (mount.accessible) return hasNumber(mount.use_pct) && mount.use_pct >= 85;
  if (virtualMount(mount) && mount.mounted) return false;
  if (!mount.covers_home && (mount.status === 'automount_pending' || (mount.status === 'unmounted' && (mount.optional || mount.noauto)))) return false;
  return true;
}
function uniqueMounts(mounts) {
  const rows = new Map();
  for (const mount of mounts) {
    // Collapse identical observations only; conflicting fstab sources remain visible.
    const key = JSON.stringify(Object.keys(mount).sort().map(key => [key, mount[key]]));
    const previous = rows.get(key);
    if (previous) previous.duplicates++;
    else rows.set(key, {...mount, duplicates:1});
  }
  return [...rows.values()];
}
export function storageSummary(reports) {
  const nodes = reports.filter(report => report.report_type === 'storage').map(report => {
    const mounts = uniqueMounts(report.mounts || []);
    let home = mounts.find(mount => mount.covers_home);
    // Older artifacts predate the explicit /home marker.
    if (!home && !mounts.some(mount => 'covers_home' in mount)) home = mounts.find(mount => mount.mountpoint === '/home');
    return {...report, mounts, home};
  });
  const groups = new Map();
  let routineCount = 0;
  for (const node of nodes) for (const mount of node.mounts) {
    if (mount === node.home) continue;
    if (!storageIssue(mount) && (['/boot','/boot/efi'].includes(mount.mountpoint) || virtualMount(mount))) {
      routineCount++;
      continue;
    }
    const fstype = mount.accessible ? mount.fstype || mount.configured_fstype : mount.configured_fstype || mount.fstype;
    const source = mount.accessible ? mount.source || mount.configured_source : mount.configured_source || mount.source;
    const shared = networkTypes.has(fstype) && !!source;
    // Local device names are only meaningful within a node. Never add capacities.
    const key = shared ? JSON.stringify([fstype === 'nfs4' ? 'nfs' : fstype, source]) : JSON.stringify([node.hostname, mount.mountpoint, source]);
    if (!groups.has(key)) groups.set(key, {key, shared, source, rows:[]});
    groups.get(key).rows.push({...mount, hostname:node.hostname});
  }
  const additional = [...groups.values()].map(group => {
    const readings = group.rows.filter(row => row.accessible);
    const sameReadings = readings.every(row => ['used_mb','total_mb','avail_mb','use_pct'].every(key => row[key] === readings[0]?.[key]));
    const states = new Map();
    for (const row of group.rows) states.set(storageState(row), (states.get(storageState(row)) || 0) + 1);
    return {...group, reading:sameReadings ? readings[0] : null, readingsDiffer:!sameReadings,
      coverage:[...states].map(([state,count]) => `${count} ${state.toLowerCase()}`).join(' · '),
      issue:group.rows.some(storageIssue)};
  });
  return {nodes, additional, routineCount};
}

export function visibleStorageOutcomes(job) {
  const results = job?.device_results || [];
  if (job?.playbook !== 'storage_analysis.yml') return results;
  const reported = new Set((job.result_artifacts || []).filter(report => report.report_type === 'storage' && report.mounts?.length).map(report => report.hostname));
  return results.filter(result => result.status !== 'success' || result.detail || result.recovery_resolution || !reported.has(result.hostname));
}
