import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {parse,compileScript} from '@vue/compiler-sfc';
import {createRenderer,nextTick} from 'vue';
import {createRouter,createMemoryHistory} from 'vue-router';

function element(tag,text='') { return {tag,text,props:{},children:[],parent:null,focus(){},scrollIntoView(){},addEventListener(){},removeEventListener(){},setAttribute(){},removeAttribute(){}}; }
const renderer=createRenderer({
 createElement:tag=>element(tag), createText:text=>element('#text',text), createComment:text=>element('#comment',text),
 setText:(node,text)=>node.text=text,setElementText:(node,text)=>{node.text=text;node.children=[];},
 patchProp:(node,key,old,value)=>node.props[key]=value,
 insert(node,parent,anchor=null){if(node.parent){node.parent.children=node.parent.children.filter(c=>c!==node);}node.parent=parent;const i=anchor?parent.children.indexOf(anchor):-1;i<0?parent.children.push(node):parent.children.splice(i,0,node);},
 remove(node){if(node.parent)node.parent.children=node.parent.children.filter(c=>c!==node);},
 parentNode:node=>node.parent,nextSibling:node=>node.parent?.children[node.parent.children.indexOf(node)+1],
});
function text(node) { return node.tag==='#comment'?'':node.text+node.children.map(text).join(''); }
function find(node,predicate) { if(predicate(node))return node;for(const child of node.children){const match=find(child,predicate);if(match)return match;} }
const flush=async()=>{for(let i=0;i<12;i++){await new Promise(resolve=>setImmediate(resolve));await nextTick();}};
async function compileView(url) {
 const source=await readFile(url,'utf8');
 const {descriptor}=parse(source);
 let code=compileScript(descriptor,{id:url.pathname,inlineTemplate:true}).content;
 const imports=[...code.matchAll(/from ['"]([^'"]+)['"]/g)];
 for(const [,name] of imports) {
  const resolved=name.endsWith('.vue')?await compileView(new URL(name,url)):name.startsWith('.')?new URL(name,url).href:import.meta.resolve(name);
  code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(resolved)}`).replaceAll(`from '${name}'`,`from ${JSON.stringify(resolved)}`);
 }
 return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`;
}
const {default:Operations}=await import(await compileView(new URL('./Operations.vue',import.meta.url)));
const devices=[{id:1,name:'Node 1',inventory_name:'node-01',discovered_at:new Date().toISOString(),facts_stale:false,transport:'ssh',os_family:'Debian',maintenance_mode:'kubernetes'},{id:2,name:'Robot',inventory_name:'robot',discovered_at:new Date().toISOString(),facts_stale:false,transport:'reachy_daemon',kind:'robot',model:'Reachy Mini Wireless'}];
const checkJob={job_id:'check-id',playbook:'package_preview.yml',target_devices:'node-01',status:'success',finished_at:new Date().toISOString(),device_results:[{hostname:'node-01',status:'success'}],result_artifacts:[{hostname:'node-01',report_type:'packages',fingerprint:'a'.repeat(64),changes:['Inst curl [1] (2 Ubuntu)'],package_count:1}]};
async function mount(query={devices:'1'},failOnce=false,recovery=false,installPhase='complete',inspectionReports=[],stale=false) {
 global.localStorage={getItem:()=> 'test'};global.window={location:{hash:''}};
 const calls=[];let posted=0;let currentJob=checkJob;let scanned=false;
 global.fetch=async(url,options={})=>{
  calls.push({url,options,body:options.body?JSON.parse(options.body):null});
  const respond=value=>new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
  if(url==='/api/v2/devices')return respond(devices.map(device=>({...device,facts_stale:stale&&!scanned,recovery_required:recovery&&device.id===1})));
  if(url==='/api/v2/operations')return respond(['system.scan','system.packages.preview','system.update','containers.cleanup','system.reboot','storage.inspect','gpu.inspect','reachy.daemon.restart'].map(id=>id==='system.scan'?{id,eligible_device_ids:[1,2],excluded_devices:[]}:stale&&!scanned?{id,eligible_device_ids:[],excluded_devices:devices.map(d=>({id:d.id,reason:'Scan devices first. Device facts are missing or stale.'}))}:id==='reachy.daemon.restart'?{id,eligible_device_ids:[2],excluded_devices:[{id:1,reason:'Requires a Reachy Mini device connected through its daemon'}]}:{id,eligible_device_ids:[1],excluded_devices:[{id:2,reason:'Requires SSH'}]}));
  if(url.startsWith('/api/v2/jobs?'))return respond([]);
  if(options.method==='POST') {
   posted++;
   if(failOnce&&posted===1)throw new Error('Connection lost');
   if(url.includes('system.packages.preview'))currentJob=checkJob;
   if(url.includes('system.scan')) {scanned=installPhase==='complete';currentJob={...checkJob,job_id:'scan-id',playbook:'host_facts.yml',target_devices:JSON.parse(options.body).device_ids.map(id=>devices.find(d=>d.id===id).inventory_name).join(','),status:installPhase==='complete'?'success':installPhase,phase:'scanning',result_artifacts:inspectionReports};}
   if(url.includes('system.update'))currentJob={...checkJob,job_id:'install-id',playbook:'system_update.yml',phase:installPhase,status:installPhase==='checking_health'?'running':installPhase==='health_check_failed'?'failed':'success',error_summary:installPhase==='health_check_failed'?'Automatic health check failed. The requested action did not start.':null,device_results:installPhase==='health_check_failed'?[{hostname:'node-01',status:'verification_failed',detail:'Required mounts are missing: /data'}]:checkJob.device_results,result_artifacts:[{report_type:'apt_install',hostname:'node-01',package_count:1,reboot_required:true}]};
   if(url.includes('system.reboot'))currentJob={...checkJob,job_id:'reboot-id',playbook:'reboot.yml',status:installPhase==='complete'?'success':installPhase,phase:'executing',error_summary:installPhase==='recovery_required'?'The node did not return over SSH.':null,result_artifacts:[{report_type:'reboot',hostname:'node-01',rebooted:true,elapsed_seconds:30}]};
   if(url.includes('reachy.daemon.restart'))currentJob={...checkJob,job_id:'restart-id',playbook:'reachy.daemon.restart',target_devices:'robot',status:installPhase==='complete'?'success':installPhase,phase:'verifying',error_summary:installPhase==='recovery_required'?'Daemon health could not be verified':null,device_results:[{hostname:'robot',status:installPhase==='complete'?'success':installPhase}],result_artifacts:[]};
   if(url.includes('storage.inspect') || url.includes('gpu.inspect'))currentJob={...checkJob,job_id:'inspection-id',playbook:url.includes('storage.inspect')?'storage_analysis.yml':'gpu_usage.yml',status:installPhase==='complete'?'success':installPhase,result_artifacts:inspectionReports};
   return respond({job_id:currentJob.job_id});
  }
  if(url.startsWith('/api/v2/jobs/'))return respond(currentJob);
  throw new Error(`Unexpected request ${url}`);
 };
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/operations',component:Operations},{path:'/:pathMatch(.*)*',component:{render:()=>null}}]});
 await router.push({path:'/operations',query});await router.isReady();
 const app=renderer.createApp(Operations).use(router),root=element('root');app.mount(root);await flush();
 const click=async label=>{const button=find(root,node=>node.tag==='button'&&text(node)===label);assert.ok(button,`Missing button ${label}`);assert.ok(!button.props.disabled,`${label} is disabled`);await button.props.onClick();await flush();};
 return {app,root,calls,click,router};
}

test('check, review and install stay on the same screen without typed confirmation',async()=>{
 const view=await mount();
 try {
  await view.click('Check now');
  assert.match(text(view.root),/1 package update available/);
  assert.equal(view.router.currentRoute.value.path,'/operations');
  await view.click('Review & install');
  assert.match(text(view.root),/Install checked apt updates\?/);
  assert.doesNotMatch(text(view.root),/drain|Kubernetes|Workload protections/);
  assert.equal(view.calls.filter(c=>c.options.method==='POST').length,1);
  // There are two install buttons: one is the inline review, one in results.
  const review=find(view.root,n=>n.tag==='section'&&n.props['aria-labelledby']==='review-heading');
  const confirm=find(review,n=>n.tag==='button'&&text(n)==='Install 1 update');
  await confirm.props.onClick();await flush();
  const posts=view.calls.filter(c=>c.options.method==='POST');
  assert.equal(posts.length,2);
  assert.deepEqual(posts[1].body.device_ids,[1]);
  assert.equal(posts[1].body.preview_job_id,'check-id');
  assert.equal(posts[1].body.confirmation,'Node 1');
  assert.match(text(view.root),/Apt updates installed/);
  assert.match(text(view.root),/Reboot required/);
 } finally {view.app.unmount();}
});

test('unsupported selected devices block the whole request instead of being silently skipped',async()=>{
 const view=await mount({devices:'1,2'});
 try {await view.click('Check now');assert.match(text(view.root),/Requires SSH/);assert.equal(view.calls.filter(c=>c.options.method==='POST').length,0);await view.click('Deselect');await view.click('Check now');assert.deepEqual(view.calls.find(c=>c.options.method==='POST').body.device_ids,[1]);}
 finally{view.app.unmount();}
});

test('ambiguous network failure retries with the same idempotency key',async()=>{
 const view=await mount({devices:'1'},true);
 try {await view.click('Check now');assert.match(text(view.root),/may have been accepted/);await view.click('Reconnect to request');const posts=view.calls.filter(c=>c.options.method==='POST');assert.equal(posts.length,2);assert.equal(posts[0].body.request_key,posts[1].body.request_key);assert.match(text(view.root),/update available/);}
 finally{view.app.unmount();}
});

test('cleanup can be cancelled without sending a request',async()=>{
 const view=await mount();
 try {await view.click('Clear cache…');assert.match(text(view.root),/Containers, volumes, and networks stay intact/);await view.click('Cancel');assert.equal(view.calls.filter(c=>c.options.method==='POST').length,0);}
 finally{view.app.unmount();}
});

test('install entry point checks automatically and opens review without installing',async()=>{
 const view=await mount();
 try {await view.click('Review & install');assert.match(text(view.root),/Install checked apt updates\?/);const posts=view.calls.filter(c=>c.options.method==='POST');assert.equal(posts.length,1);assert.match(posts[0].url,/system.packages.preview/);assert.doesNotMatch(posts[0].url,/system.update/);}
 finally{view.app.unmount();}
});


for (const phase of ['complete','checking_health','health_check_failed']) {
 test(`automatic recovery stays in the install flow: ${phase}`,async()=>{
  const view=await mount({devices:'1'},false,true,phase);
  try {
   assert.match(text(view.root),/Health checks run before install or cleanup/);
   assert.ok(!find(view.root,n=>n.tag==='button'&&/verify/i.test(text(n))));
   await view.click('Review & install');
   assert.match(text(view.root),/then continue automatically/);
   assert.equal(view.calls.filter(c=>c.options.method==='POST').length,1);
   const review=find(view.root,n=>n.tag==='section'&&n.props['aria-labelledby']==='review-heading');
   await find(review,n=>n.tag==='button'&&text(n)==='Install 1 update').props.onClick();await flush();
   const posts=view.calls.filter(c=>c.options.method==='POST');
   assert.equal(posts.length,2);
   assert.match(posts[1].url,/system.update/);
   assert.ok(!view.calls.some(c=>c.url.includes('/scan')));
   if(phase==='checking_health') {
    assert.match(text(view.root),/Checking device health/);
    assert.match(text(view.root),/Your action will continue automatically/);
   } else if(phase==='health_check_failed') {
    assert.match(text(view.root),/The requested action did not start/);
    assert.match(text(view.root),/Required mounts are missing: \/data/);
   } else assert.match(text(view.root),/Apt updates installed/);
  } finally {view.app.unmount();}
 });
}


for (const state of ['complete','running','recovery_required']) {
 test(`unconditional reboot confirms once without package or health prerequisites: ${state}`,async()=>{
  const view=await mount({devices:'1',operation:'system.reboot'},false,true,state);
  try {
   await view.click('Reboot…');
   assert.match(text(view.root),/Reboot selected nodes\?/);
   assert.match(text(view.root),/Running work will be interrupted/);
   assert.doesNotMatch(text(view.root),/then continue automatically/);
   assert.equal(view.calls.filter(c=>c.options.method==='POST').length,0);
   await view.click('Reboot now');
   const posts=view.calls.filter(c=>c.options.method==='POST');
   assert.equal(posts.length,1);
   assert.match(posts[0].url,/system.reboot/);
   assert.deepEqual(posts[0].body.device_ids,[1]);
   assert.equal(posts[0].body.confirmation,'Node 1');
   assert.equal(posts[0].body.preview_job_id,undefined);
   assert.ok(!view.calls.some(c=>c.url.includes('/scan')));
   if(state==='complete')assert.match(text(view.root),/Nodes rebooted/);
   else if(state==='running')assert.match(text(view.root),/waiting for SSH to return/);
   else assert.match(text(view.root),/The node did not return over SSH/);
  } finally {view.app.unmount();}
 });
}

test('reboot confirmation can be cancelled without sending a request',async()=>{
 const view=await mount();
 try {await view.click('Reboot…');await view.click('Cancel');assert.equal(view.calls.filter(c=>c.options.method==='POST').length,0);}
 finally {view.app.unmount();}
});

const storageReports=[{hostname:'node-01',report_type:'storage',timestamp:'2026-10-10T12:00:00Z',mounts:[
 {mountpoint:'/',source:'/dev/sda1',fstype:'ext4',covers_home:true,in_fstab:true,status:'mounted',accessible:true,total_mb:1024,used_mb:0,avail_mb:1024,use_pct:0},
 {mountpoint:'/data',configured_source:'nas:/data',status:'unmounted',accessible:false,optional:true,noauto:true},
]}];
const gpuReports=[{hostname:'node-01',report_type:'gpu',gpus:[{index:0,uuid:'GPU-a',name:'Test GPU',utilization_pct:null,memory_supported:false,status:'in_use',processes_known:true,processes:[
 {pid:42,user:'alice',uid:1001,process_name:'/usr/bin/python',gpu_memory_mb:null,namespace:'team',pod_name:'inference',workload_owner:'bob',gpu_instance_id:'2',compute_instance_id:'1'},
]}]}];
for(const [id,cta,reports,expected] of [['storage.inspect','Check storage',storageReports,/Storage check completed/],['gpu.inspect','Check GPUs',gpuReports,/GPU check completed/]]) {
 test(`${id} runs once without confirmation and renders detailed results`,async()=>{
  const view=await mount({devices:'1',operation:id},false,true,'complete',reports);
  try {
   await view.click(cta);
   const posts=view.calls.filter(c=>c.options.method==='POST');
   assert.equal(posts.length,1);assert.ok(posts[0].url.includes(id));assert.deepEqual(posts[0].body.device_ids,[1]);
   assert.equal(posts[0].body.preview_job_id,undefined);assert.match(text(view.root),expected);
   assert.ok(!find(view.root,n=>n.props['aria-labelledby']==='review-heading'));
   if(id==='storage.inspect') {
    assert.match(text(view.root),/Contains \/home/);assert.match(text(view.root),/Not mounted/);
    assert.match(text(view.root),/Optional \(nofail\)/);assert.match(text(view.root),/0%/);
   } else {
    assert.match(text(view.root),/Unavailable utilization/);assert.match(text(view.root),/alice/);
    assert.match(text(view.root),/42/);assert.match(text(view.root),/team\/inference/);
    assert.match(text(view.root),/Owner label: bob/);assert.doesNotMatch(text(view.root),/0% utilization/);
   }
  } finally {view.app.unmount();}
 });
}

test('GPU check blocks incompatible selections instead of skipping them',async()=>{
 const view=await mount({devices:'1,2',operation:'gpu.inspect'});
 try {await view.click('Check GPUs');assert.match(text(view.root),/Requires SSH/);assert.equal(view.calls.filter(c=>c.options.method==='POST').length,0);}
 finally {view.app.unmount();}
});

test('partial inspection preserves successful results and per-device errors',async()=>{
 const view=await mount({devices:'1'},false,false,'partial',storageReports);
 try {await view.click('Check storage');assert.match(text(view.root),/Some devices need attention/);assert.match(text(view.root),/Contains \/home/);}
 finally {view.app.unmount();}
});

for (const state of ['complete','running','recovery_required']) {
 test(`Reachy Mini restart confirms targets and shows daemon progress: ${state}`,async()=>{
  const view=await mount({devices:'2',operation:'reachy.daemon.restart'},false,false,state);
  try {
   await view.click('Restart daemon…');
   assert.match(text(view.root),/Restart Reachy Mini daemon\?/);
   assert.match(text(view.root),/Connected apps are interrupted/);
   assert.match(text(view.root),/robot may move/);
   assert.equal(view.calls.filter(c=>c.options.method==='POST').length,0);
   await view.click('Restart daemon');
   const posts=view.calls.filter(c=>c.options.method==='POST');
   assert.equal(posts.length,1);
   assert.match(posts[0].url,/reachy.daemon.restart/);
   assert.deepEqual(posts[0].body.device_ids,[2]);
   assert.equal(posts[0].body.confirmation,'Robot');
   assert.equal(posts[0].body.preview_job_id,undefined);
   if(state==='complete')assert.match(text(view.root),/Reachy Mini daemon restarted/);
   else if(state==='running')assert.match(text(view.root),/waiting for the robot backend to be ready/);
   else assert.match(text(view.root),/Daemon health could not be verified/);
  } finally {view.app.unmount();}
 });
}

test('Reachy Mini restart is hidden when only SSH nodes are selected',async()=>{
 const view=await mount({devices:'1'});
 try {assert.doesNotMatch(text(view.root),/Restart daemon…/);}
 finally {view.app.unmount();}
});

test('mixed Reachy Mini and SSH selection blocks the entire daemon restart',async()=>{
 const view=await mount({devices:'1,2'});
 try {
  await view.click('Restart daemon…');
  assert.match(text(view.root),/Requires a Reachy Mini device/);
  assert.equal(view.calls.filter(c=>c.options.method==='POST').length,0);
  await view.click('Deselect');
  await view.click('Restart daemon…');
  await view.click('Restart daemon');
  assert.deepEqual(view.calls.find(c=>c.options.method==='POST').body.device_ids,[2]);
 } finally {view.app.unmount();}
});

test('Reachy Mini restart can be cancelled before dispatch',async()=>{
 const view=await mount({devices:'2'});
 try {await view.click('Restart daemon…');await view.click('Cancel');assert.equal(view.calls.filter(c=>c.options.method==='POST').length,0);}
 finally {view.app.unmount();}
});

test('Reachy Mini restart reconnects to an uncertain request with the same key',async()=>{
 const view=await mount({devices:'2'},true);
 try {
  await view.click('Restart daemon…');await view.click('Restart daemon');
  await view.click('Reconnect to request');
  const posts=view.calls.filter(c=>c.options.method==='POST');
  assert.equal(posts.length,2);assert.deepEqual(posts[0].body,posts[1].body);
  assert.match(text(view.root),/Reachy Mini daemon restarted/);
 } finally {view.app.unmount();}
});


test('scan prerequisite refreshes facts and eligibility before another action',async()=>{
 const reports=[{report_type:'discovery',hostname:'node-01',device_id:1,observed_at:new Date().toISOString(),os_version:'Ubuntu 24.04',architecture:'x86_64',capabilities:['system.update'],facts:{package_manager:'apt',cpu:{model:'Test CPU'}}}];
 const view=await mount({devices:'1',operation:'system.update'},false,false,'complete',reports,true);
 try {
  assert.match(text(view.root),/Scan devices before other actions/);
  await view.click('Check now');
  assert.equal(view.calls.filter(c=>c.options.method==='POST').length,0);
  await view.click('Scan selected devices');
  assert.match(text(view.root),/Device scan completed/);
  assert.match(text(view.root),/Ubuntu 24.04/);assert.match(text(view.root),/Test CPU/);
  assert.doesNotMatch(text(view.root),/Scan devices before other actions/);
  assert.equal(view.calls.filter(c=>c.options.method==='POST').length,1);
  await view.click('Check now');
  assert.equal(view.calls.filter(c=>c.options.method==='POST').length,2);
  assert.match(text(view.root),/1 package update available/);
 } finally {view.app.unmount();}
});

test('mixed scan runs exactly the selection and reconnects with the same request key',async()=>{
 const view=await mount({devices:'1,2',operation:'system.scan'},true,false,'complete',[],true);
 try {
  await view.click('Scan now');await view.click('Reconnect to request');
  const posts=view.calls.filter(c=>c.options.method==='POST');
  assert.equal(posts.length,2);assert.deepEqual(posts[0].body,posts[1].body);
  assert.deepEqual(posts[0].body.device_ids,[1,2]);
  assert.match(posts[0].url,/system.scan/);
  assert.match(text(view.root),/Device scan completed/);
 } finally {view.app.unmount();}
});

test('failed scan leaves the prerequisite visible and blocks actions',async()=>{
 const view=await mount({devices:'1'},false,false,'failed',[],true);
 try {
  await view.click('Scan now');
  assert.match(text(view.root),/This operation needs attention/);
  assert.match(text(view.root),/Scan devices before other actions/);
  await view.click('Reboot…');
  assert.equal(view.calls.filter(c=>c.options.method==='POST').length,1);
 } finally {view.app.unmount();}
});

test('scan shows the recommended hostname and copies its command without another operation',async()=>{
 const reports=[{report_type:'discovery',hostname:'node-01',device_id:1,facts:{recommended_hostname:'ai-sae-spark-abc123',hostname_recommendation_source:'Baseboard serial number'}}];
 const copied=[];
 const originalNavigator=Object.getOwnPropertyDescriptor(globalThis,'navigator');
 Object.defineProperty(globalThis,'navigator',{configurable:true,value:{clipboard:{writeText:async value=>copied.push(value)}}});
 const view=await mount({devices:'1',operation:'system.scan'},false,false,'complete',reports);
 try {
  await view.click('Scan now');
  assert.match(text(view.root),/Recommended hostname/);
  assert.match(text(view.root),/ai-sae-spark-abc123/);
  assert.match(text(view.root),/Last six characters of baseboard serial number/);
  await view.click('Copy command');
  assert.deepEqual(copied,['sudo hostnamectl set-hostname ai-sae-spark-abc123']);
  assert.match(text(view.root),/Command copied/);
  assert.equal(view.calls.filter(c=>c.options.method==='POST').length,1);
 } finally {
  view.app.unmount();
  if(originalNavigator)Object.defineProperty(globalThis,'navigator',originalNavigator);
  else delete globalThis.navigator;
 }
});

test('scan explains an unavailable recommendation and does not offer a command',async()=>{
 const reports=[{report_type:'discovery',hostname:'node-01',device_id:1,facts:{recommended_hostname:null,hostname_recommendation_reason:'No usable hardware serial number with a six-character suffix was reported.'}}];
 const view=await mount({devices:'1',operation:'system.scan'},false,false,'complete',reports);
 try {
  await view.click('Scan now');
  assert.match(text(view.root),/Recommended hostname/);
  assert.match(text(view.root),/Unavailable: No usable hardware serial number/);
  assert.ok(!find(view.root,n=>n.tag==='button'&&text(n)==='Copy command'));
 } finally {view.app.unmount();}
});
