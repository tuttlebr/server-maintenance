import test from 'node:test';
import assert from 'node:assert/strict';
import {validPackageCheck, blockers, packageCount} from './maintenance.js';
const devices=[{id:1,inventory_name:'node-01',name:'Node 1'},{id:2,inventory_name:'node-02',name:'Node 2'}];
const now=Date.parse('2026-10-09T16:00:00Z');
const preview={playbook:'package_preview.yml',status:'success',target_devices:'node-01,node-02',finished_at:'2026-10-09T15:50:00',result_artifacts:devices.map(d=>({hostname:d.inventory_name,report_type:'packages',fingerprint:'a'.repeat(64),changes:['Inst openssl [1] (2 Ubuntu)','Conf openssl (2 Ubuntu)']}))};
test('package review requires fresh complete evidence and exact selected devices',()=>{
 assert.equal(validPackageCheck(preview,devices,now),true);
 assert.equal(validPackageCheck(preview,[],now),false);
 assert.equal(validPackageCheck(preview,devices.slice(0,1),now),false);
 assert.equal(validPackageCheck({...preview,status:'partial'},devices,now),false);
 assert.equal(validPackageCheck({...preview,finished_at:'2026-10-09T15:30:00Z'},devices,now),false);
 assert.equal(validPackageCheck({...preview,finished_at:null},devices,now),false);
 assert.equal(validPackageCheck({...preview,result_artifacts:preview.result_artifacts.slice(0,1)},devices,now),false);
});
test('package counts do not count configuration lines as extra updates',()=>assert.equal(packageCount(preview),2));
test('ineligible and deleted devices remain explicit blockers',()=>{
 const operation={eligible_device_ids:[1],excluded_devices:[{id:2,reason:'Needs SSH'}]};
 assert.deepEqual(blockers(operation,[1,2,9],devices),[{id:2,name:'Node 2',reason:'Needs SSH'},{id:9,name:'Device #9',reason:'This device is no longer available.'}]);
 assert.deepEqual(blockers(operation,[],devices),[]);
});
