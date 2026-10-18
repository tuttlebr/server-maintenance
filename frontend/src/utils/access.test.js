import test from 'node:test';
import assert from 'node:assert/strict';
import { accountPlacement, privilegeLabel } from './access.js';
test('privilege state comes from the selected device and unverified states stay unknown', () => {
  const user = {is_sudoer:true, placements:[{device_id:1,state:'observed',managed_sudo:true},{device_id:2,state:'observed',managed_sudo:false}]};
  assert.equal(privilegeLabel(accountPlacement(user,1)), 'Managed grant present');
  assert.equal(privilegeLabel(accountPlacement(user,2)), 'No managed grant');
  assert.equal(privilegeLabel(accountPlacement(user,3)), 'Not verified');
  assert.equal(privilegeLabel({state:'unverified',managed_sudo:true}), 'Not verified');
});
