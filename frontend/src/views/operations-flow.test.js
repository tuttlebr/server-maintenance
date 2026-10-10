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
const devices=[{id:1,name:'Node 1',inventory_name:'node-01',transport:'ssh',os_family:'Debian',maintenance_mode:'kubernetes'},{id:2,name:'Robot',inventory_name:'robot',transport:'reachy_daemon'}];
const checkJob={job_id:'check-id',playbook:'package_preview.yml',target_devices:'node-01',status:'success',finished_at:new Date().toISOString(),device_results:[{hostname:'node-01',status:'success'}],result_artifacts:[{hostname:'node-01',report_type:'packages',fingerprint:'a'.repeat(64),changes:['Inst curl [1] (2 Ubuntu)'],package_count:1}]};
async function mount(query={devices:'1'},failOnce=false,recovery=false,installPhase='complete') {
 global.localStorage={getItem:()=> 'test'};global.window={location:{hash:''}};
 const calls=[];let posted=0;let currentJob=checkJob;
 global.fetch=async(url,options={})=>{
  calls.push({url,options,body:options.body?JSON.parse(options.body):null});
  const respond=value=>new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
  if(url==='/api/v2/devices')return respond(devices.map(device=>({...device,recovery_required:recovery&&device.id===1})));
  if(url==='/api/v2/operations')return respond(['system.packages.preview','system.update','containers.cleanup','system.reboot'].map(id=>({id,eligible_device_ids:[1],excluded_devices:[{id:2,reason:'Requires SSH'}]})));
  if(url.startsWith('/api/v2/jobs?'))return respond([]);
  if(options.method==='POST') {
   posted++;
   if(failOnce&&posted===1)throw new Error('Connection lost');
   if(url.includes('system.update'))currentJob={...checkJob,job_id:'install-id',playbook:'system_update.yml',phase:installPhase,status:installPhase==='checking_health'?'running':installPhase==='health_check_failed'?'failed':'success',error_summary:installPhase==='health_check_failed'?'Automatic health check failed. The requested action did not start.':null,device_results:installPhase==='health_check_failed'?[{hostname:'node-01',status:'verification_failed',detail:'Required mounts are missing: /data'}]:checkJob.device_results,result_artifacts:[{report_type:'apt_install',hostname:'node-01',package_count:1,reboot_required:true}]};
   if(url.includes('system.reboot'))currentJob={...checkJob,job_id:'reboot-id',playbook:'reboot.yml',status:installPhase==='complete'?'success':installPhase,phase:'executing',error_summary:installPhase==='recovery_required'?'The node did not return over SSH.':null,result_artifacts:[{report_type:'reboot',hostname:'node-01',rebooted:true,elapsed_seconds:30}]};
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
