// An empty selection must never widen an operation to the whole fleet.
export function selectedOperationTargets(operation, selectedIds) {
  const eligible = new Set(operation.eligible_device_ids);
  return [...new Set(selectedIds)].filter((id) => eligible.has(id));
}
