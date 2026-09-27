import test from 'node:test';
import assert from 'node:assert/strict';
import { attentionGroups, deviceConditions, diskPercent, completedSummary, fleetCoverage, groupRoute, parseDeviceIds, overlappingJobs } from './fleetOverview.js';
const device = (id, extra = {}) => ({ id, name: `node-${String(id).padStart(3, '0')}`, inventory_name: `host-${id}`, status: 'online', discovered_at: '2026-09-25T12:00:00Z', capabilities: [], ...extra });

test('recovery on device 200 outranks 199 storage alerts without losing any scope', () => {
  const fleet = Array.from({length: 200}, (_, i) => device(i + 1, i === 199 ? {recovery_required:true} : {disk_root_percent:86}));
  const groups = attentionGroups(fleet);
  assert.deepEqual(groups.map(group => [group.id, group.devices.length]), [['recovery',1],['storage',199]]);
  assert.equal(groupRoute(groups[0]).query.operation, 'system.recover');
  assert.equal(groupRoute(groups[0]).query.devices, '200');
  assert.equal(parseDeviceIds(groupRoute(groups[1]).query.devices).length, 199);
  assert.equal(groupRoute(groups[1]).query.operation, 'storage.inspect');
});
test('overlapping reasons remain explicit; storage ranks by pressure, not name', () => {
  const fleet = [device(1,{disk_root_percent:85}),device(2,{disk_root_percent:97,recovery_required:true,reboot_required:true,facts_stale:true})];
  const groups = attentionGroups(fleet);
  assert.equal(new Set(groups.flatMap(group => group.devices.map(device => device.id))).size,2);
  assert.deepEqual(groups.find(group => group.id === 'storage').devices.map(device => device.id),[2,1]);
  assert.deepEqual(deviceConditions(fleet[1]).map(condition => condition.id),['recovery','storage','verification','reboot']);
});
test('absent and invalid readings remain unknown while real zero stays reported', () => {
  for (const value of [null, undefined, NaN, Infinity, -1, 101, '90']) assert.equal(diskPercent({disk_root_percent:value}),null);
  const coverage = fleetCoverage([device(1,{disk_root_percent:0}),device(2),device(3,{disk_root_percent:91,facts_stale:true})]);
  assert.deepEqual([coverage.reported,coverage.missing,coverage.stale,coverage.worst],[2,1,1,91]);
  assert.equal(fleetCoverage([]).worst,null);
  assert.equal(deviceConditions(device(1,{discovered_at:null}))[0].label,'No discovery recorded');
});
test('outcome sample excludes active and unrecognized states, keeps recovery and cancellation distinct', () => {
  const summary = completedSummary(['success','partial','failed','recovery_required','cancelled','running','pending','cancelling','unknown'].map(status => ({status})));
  assert.equal(summary.total,5);
  assert.deepEqual(summary.counts,{success:1,partial:1,failed:1,recovery_required:1,cancelled:1});
});
test('active overlap uses exact inventory identities, never display-name guesses', () => {
  const jobs = [{status:'running',target_devices:'host-1, host-2'}, {status:'success',target_devices:'host-1'}, {status:'pending',target_devices:'node-001'}, {status:'running',target_devices:'host-10'}];
  assert.deepEqual(overlappingJobs([device(1)],jobs),[jobs[0]]);
});
test('empty or malformed scope never expands; composition categories are disjoint', () => {
  assert.deepEqual(parseDeviceIds(''),[]);
  assert.deepEqual(parseDeviceIds('1,1,2,0,-3,NaN,4x,1e2,9007199254740993'),[1,2]);
  const coverage = fleetCoverage([device(1,{kind:'robot',capabilities:['gpu.inspect']}),device(2,{capabilities:['gpu.inspect']}),device(3)]);
  assert.deepEqual([coverage.robots,coverage.gpu,coverage.other],[1,1,1]);
});
