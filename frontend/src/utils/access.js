export function accountPlacement(user, deviceId) {
  return user?.placements?.find(item => item.device_id === deviceId) || { device_id: deviceId, state: 'unverified', managed_sudo: null };
}
export function privilegeLabel(placement) {
  if (placement.state === 'absent') return 'Account absent';
  if (placement.state !== 'observed' || placement.managed_sudo == null) return 'Not verified';
  return placement.managed_sudo ? 'Managed grant present' : 'No managed grant';
}
