import test from 'node:test';
import assert from 'node:assert/strict';
import {storageSummary, storageState, storageIssue, visibleStorageOutcomes} from './storage.js';

const home = {mountpoint:'/',source:'/dev/sda1',fstype:'ext4',covers_home:true,accessible:true,total_mb:1000,used_mb:400,avail_mb:600,use_pct:40};
const share = {mountpoint:'/data',source:'nas:/data',configured_source:'nas:/data',fstype:'nfs4',configured_fstype:'nfs',accessible:true,mounted:true,total_mb:8000,used_mb:4000,avail_mb:4000,use_pct:50,status:'mounted'};
const pending = {...share,source:'systemd-1',fstype:'autofs',accessible:false,mounted:false,total_mb:null,used_mb:null,avail_mb:null,use_pct:null,status:'automount_pending'};
const report = (hostname,mounts) => ({report_type:'storage',hostname,mounts});

test('shared capacity is shown once while keeping each node mount state',()=>{
  const summary=storageSummary([report('one',[home,share]),report('two',[home,pending])]);
  assert.equal(summary.nodes.length,2);
  assert.equal(summary.additional.length,1);
  const group=summary.additional[0];
  assert.equal(group.reading.total_mb,8000);
  assert.equal(group.rows.length,2);
  assert.match(group.coverage,/1 mounted.*1 on demand/);
  assert.equal(group.issue,false);
});

test('differing shared observations are retained instead of summed or arbitrarily chosen',()=>{
  const group=storageSummary([report('one',[home,share]),report('two',[home,{...share,used_mb:5000,use_pct:63}])]).additional[0];
  assert.equal(group.readingsDiffer,true);
  assert.equal(group.reading,null);
  assert.deepEqual(group.rows.map(row=>row.used_mb),[4000,5000]);
});

test('local devices, distinct exports, and conflicting sources stay separate',()=>{
  const local={...share,source:'/dev/sdb1',configured_source:'/dev/sdb1',fstype:'ext4',configured_fstype:'ext4'};
  const summary=storageSummary([report('one',[home,local,share,{...share,source:'nas:/other',configured_source:'nas:/other'}]),report('two',[home,local])]);
  assert.equal(summary.additional.length,4);
  assert.equal(summary.additional.filter(group=>!group.shared).length,2);
});

test('identical fstab entries collapse with a count; conflicting entries are preserved',()=>{
  const summary=storageSummary([report('one',[home,pending,{...pending},{...pending,configured_source:'nas:/elsewhere'}])]);
  assert.equal(summary.nodes[0].mounts.length,3);
  assert.equal(summary.nodes[0].mounts[1].duplicates,2);
  assert.equal(summary.additional.length,2);
});

test('healthy boot and mounted virtual entries fold away but real problems remain prominent',()=>{
  const boot={...home,covers_home:false,mountpoint:'/boot'};
  const virtual={mountpoint:'/sys/kernel/security',fstype:'securityfs',mounted:true,accessible:false,status:'unavailable'};
  const summary=storageSummary([report('one',[home,boot,virtual,{...boot,mountpoint:'/boot/efi',use_pct:95}])]);
  assert.equal(summary.routineCount,2);
  assert.equal(summary.additional.length,1);
  assert.equal(summary.additional[0].issue,true);
  assert.equal(storageState(virtual),'Virtual filesystem');
  assert.equal(storageIssue({...virtual,mounted:false,status:'unmounted'}),true);
  assert.equal(storageIssue({...pending,covers_home:true}),true);
});

test('legacy and empty reports remain usable without inventing capacity',()=>{
  const legacy={...home};delete legacy.covers_home;
  const summary=storageSummary([report('one',[legacy]),report('two',[]),report('three',[home,pending])]);
  assert.equal(summary.nodes[0].home,undefined);
  assert.equal(summary.nodes[1].home,undefined);
  const shared=summary.additional.find(group=>group.shared);
  assert.equal(shared.reading,undefined);
  assert.match(shared.coverage,/on demand/);
});

test('only redundant successful outcomes are removed; missing reports and errors remain',()=>{
  const job={playbook:'storage_analysis.yml',result_artifacts:[report('one',[home]),report('empty',[])],device_results:[{hostname:'one',status:'success'},{hostname:'missing',status:'success'},{hostname:'empty',status:'success'},{hostname:'failed',status:'failed',detail:'SSH unavailable'}]};
  assert.deepEqual(visibleStorageOutcomes(job).map(row=>row.hostname),['missing','empty','failed']);
  assert.equal(visibleStorageOutcomes({...job,playbook:'gpu_usage.yml'}).length,4);
});
