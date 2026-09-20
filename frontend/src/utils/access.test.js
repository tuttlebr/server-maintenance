import test from 'node:test';
import assert from 'node:assert/strict';
import { accountPlacement, privilegeLabel, exactPreviewTargets } from './access.js';
test('privilege state comes from the selected device and unverified states stay unknown', () => {
  const user = {is_sudoer:true, placements:[{device_id:1,state:'observed',managed_sudo:true},{device_id:2,state:'observed',managed_sudo:false}]};
  assert.equal(privilegeLabel(accountPlacement(user,1)), 'Managed grant present');
  assert.equal(privilegeLabel(accountPlacement(user,2)), 'No managed grant');
  assert.equal(privilegeLabel(accountPlacement(user,3)), 'Not verified');
  assert.equal(privilegeLabel({state:'unverified',managed_sudo:true}), 'Not verified');
});
test('package approval binds exact targets and expires after thirty minutes', () => {
  const now=Date.parse('2026-09-20T14:00:00Z');
  const devices=[{id:1,inventory_name:'one'},{id:2,inventory_name:'two'}];
  const job={playbook:'package_preview.yml',status:'success',finished_at:'2026-09-20T13:50:00',target_devices:'one,two'};
  assert.equal(exactPreviewTargets(job,devices,[2,1],now),true);
  assert.equal(exactPreviewTargets(job,devices,[1],now),false);
  assert.equal(exactPreviewTargets(job,devices,[],now),false);
  assert.equal(exactPreviewTargets(job,devices,[1,2],now+30*60*1000),false);
  assert.equal(exactPreviewTargets({...job,status:'failed'},devices,[1,2],now),false);
});
