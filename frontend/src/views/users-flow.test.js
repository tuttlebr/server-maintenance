import test from 'node:test';
import assert from 'node:assert/strict';
import {createRouter,createMemoryHistory} from 'vue-router';

import {element,renderer,text,find,flush,compileView} from '../../test-support/vue.js';

const {default:Users}=await import(await compileView(new URL('./UserManagement.vue',import.meta.url)));
const devices=[{id:1,name:'Node 1',inventory_name:'node-01',discovered_at:new Date().toISOString(),transport:'ssh',capabilities:['users.manage'],os_family:'Debian',facts_stale:false,recovery_required:true},{id:2,name:'Node 2',inventory_name:'node-02',discovered_at:new Date().toISOString(),transport:'ssh',capabilities:['users.manage']}];
async function mount({query={devices:'1'},failOnce=false,csvError=false,jobState='success',stale=false,initialMode='add',accountsAfter=null,inspectState='success',inspectFailOnce=false}={}) {
 global.Document=class Document {};global.ShadowRoot=class ShadowRoot {};global.document={activeElement:null};global.localStorage={getItem:()=> 'test'};global.window={location:{hash:''}};
 const calls=[];let posted=0,inspected=0,jobPolls=0;
 global.fetch=async(url,options={})=>{
  const body=options.body instanceof FormData ? options.body : options.body?JSON.parse(options.body):null;
  calls.push({url,options,body});
  const respond=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
  if(url==='/api/v2/devices')return respond(devices.map(d=>({...d,facts_stale:stale})));
  if(url==='/api/v2/users')return respond((inspected && accountsAfter) || [{id:1,username:'jane',full_name:'Jane',placements:[{device_id:1,state:'observed',groups:'users',shell:'/bin/bash'}]}]);
  if(url==='/api/v2/users/csv-preview')return csvError?respond({detail:'Row 3: duplicate username jane'},400):respond({users:body.get('mode')==='edit'?[{username:'jane',groups:'dev,docker',shell:'/bin/bash'},{username:'sam',full_name:'Sam Updated'}]:[{username:'jane',full_name:'Doe, Jane',email:'jane@example.com'},{username:'sam',full_name:'Sam'}]});
  if(url==='/api/v2/users/inspect'){
   inspected++;if(inspectFailOnce&&inspected===1)throw new Error('Connection lost');
   return respond({job_id:'inspect-job'});
  }
  if(/^\/api\/v2\/jobs\/inspect-job(?:\/progress)?$/.test(url))return respond({job_id:'inspect-job',playbook:'access_inspect.yml',status:inspectState,device_results:[{hostname:'node-01',status:inspectState,detail:inspectState==='failed'?'SSH connection failed':undefined}],result_artifacts:[]});
  if(options.method==='POST'||options.method==='PUT'){
   posted++;if(failOnce&&posted===1)throw new Error('Connection lost');
   return respond({job_id:'user-job'});
  }
  if(/^\/api\/v2\/jobs\/user-job(?:\/progress)?$/.test(url)){
   const state=Array.isArray(jobState)?jobState[Math.min(jobPolls++,jobState.length-1)]:jobState;
   return respond({job_id:'user-job',playbook:'user_management.yml',status:state,phase:state==='running'?'checking_health':'complete',device_results:[{hostname:'node-01',status:state,detail:state==='partial'?'Account sam does not exist':undefined}],result_artifacts:[]});
  }
  throw new Error(`Unexpected request ${url}`);
 };
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/access',component:Users},{path:'/:pathMatch(.*)*',component:{render:()=>null}}]});
 await router.push({path:'/access',query});await router.isReady();
 const app=renderer.createApp(Users).use(router),root=element('root');app.mount(root);await flush();
 const click=async label=>{const b=find(root,n=>n.tag==='button'&&text(n)===label);assert.ok(b,`Missing ${label}`);assert.ok(!b.props.disabled,`${label} disabled`);await b.props.onClick();await flush();};
 const input=async(label,value)=>{const el=find(root,n=>n.props['aria-label']===label);assert.ok(el,`Missing ${label}`);el.props['onUpdate:modelValue'](value);await flush();};
 const upload=async()=>{const file=find(root,n=>n.tag==='input'&&n.props.type==='file');await file.props.onChange({target:{files:[new File(['test'],'users.csv',{type:'text/csv'})],value:'users.csv'}});await flush();};
 if(initialMode !== 'accounts')await click(initialMode==='add'?'Add users':'Edit users');
 return{app,root,calls,router,click,input,upload};
}
const mutations=view=>view.calls.filter(c=>['POST','PUT'].includes(c.options.method)&&!c.url.endsWith('csv-preview')&&!c.url.endsWith('/inspect'));

test('manual add derives a username, confirms scope once and shows completion inline',async()=>{
 const v=await mount();try{
  await v.input('Full name row 1','Jane Doe');await v.input('Email row 1','jane@example.com');
  await v.click('Review additions');assert.match(text(v.root),/Add 1 user on 1 device/);assert.equal(mutations(v).length,0);
  assert.match(text(v.root),/Pending health checks run automatically/);
  await v.click('Add users now');const call=mutations(v)[0];assert.deepEqual(call.body.device_ids,[1]);assert.equal(call.body.users[0].username,'jane');assert.ok(call.body.request_key);
  assert.match(text(v.root),/Account changes completed/);assert.equal(v.router.currentRoute.value.path,'/access');assert.ok(!v.calls.some(c=>c.url.includes('/scan')));
 }finally{v.app.unmount();}
});

test('CSV adds populate editable rows and do not launch work before confirmation',async()=>{
 const v=await mount();try{
  await v.upload();assert.equal(mutations(v).length,0);assert.match(text(v.root),/2 users imported/);
  await v.input('Full name row 2','Sam Corrected');await v.click('Review additions');await v.click('Add users now');
  assert.equal(mutations(v)[0].body.users[1].full_name,'Sam Corrected');assert.equal(mutations(v)[0].body.users.length,2);
 }finally{v.app.unmount();}
});

test('CSV edits preserve per-user changes and omit blank fields',async()=>{
 const v=await mount();try{
  await v.click('Edit users');await v.upload();assert.equal(mutations(v).length,0);
  await v.click('Review changes');await v.click('Apply changes');const call=mutations(v)[0];assert.equal(call.options.method,'PUT');assert.deepEqual(call.body.users,[{username:'jane',groups:'dev,docker',shell:'/bin/bash'},{username:'sam',full_name:'Sam Updated'}]);
 }finally{v.app.unmount();}
});

test('invalid imports and incomplete manual rows never submit partial data',async()=>{
 const v=await mount({csvError:true});try{
  await v.upload();assert.match(text(v.root),/Row 3: duplicate/);
  await v.input('Username row 1','jane');await v.click('Review additions');assert.match(text(v.root),/Row 1: Full name is required/);assert.equal(mutations(v).length,0);
 }finally{v.app.unmount();}
});

test('ambiguous account request freezes scope and retries the identical payload',async()=>{
 const v=await mount({failOnce:true});try{
  await v.upload();await v.click('Review additions');await v.click('Add users now');assert.match(text(v.root),/may have been accepted/);
  const back=find(v.root,n=>n.tag==='button'&&text(n)==='Back to editing');assert.equal(back.props.disabled,true);
  await v.click('Reconnect to request');assert.deepEqual(mutations(v)[0].body,mutations(v)[1].body);assert.match(text(v.root),/Account changes completed/);
 }finally{v.app.unmount();}
});

test('account selection supports bulk edits and mode changes preserve draft rows',async()=>{
 const v=await mount();try{
  await v.input('Full name row 1','Draft');await v.click('Accounts');await v.input('Select jane',['jane']);await v.click('Edit 1 users');await v.input('Groups row 1','dev');
  await v.click('Add users');assert.equal(find(v.root,n=>n.props['aria-label']==='Full name row 1').props.value,'Draft');await v.click('Edit users');await v.click('Review changes');await v.click('Apply changes');assert.deepEqual(mutations(v)[0].body.users,[{username:'jane',groups:'dev'}]);
 }finally{v.app.unmount();}
});

for(const state of ['running','partial'])test(`account progress reports ${state} truthfully`,async()=>{
 const v=await mount({jobState:state});try{
  await v.upload();await v.click('Review additions');await v.click('Add users now');
  if(state==='running')assert.match(text(v.root),/Checking device health before making changes/);
  else{assert.match(text(v.root),/Some devices need attention/);assert.match(text(v.root),/Account sam does not exist/);assert.doesNotMatch(text(v.root),/Account changes completed/);}
 }finally{v.app.unmount();}
});

test('missing selected devices block review without shrinking the selection',async()=>{
 const v=await mount({query:{devices:'1,99'}});try{
  assert.match(text(v.root),/Unavailable devices: 99/);assert.equal(find(v.root,n=>n.tag==='button'&&text(n)==='Review additions').props.disabled,true);assert.equal(mutations(v).length,0);
 }finally{v.app.unmount();}
});

test('account actions require a current scan and link to selected discovery targets',async()=>{
 const view=await mount({query:{devices:'1,2'},stale:true});
 try {
  assert.match(text(view.root),/Scan devices before managing accounts/);
  const button=find(view.root,n=>n.tag==='button'&&text(n)==='Review additions');
  assert.equal(button.props.disabled,true);
  const link=find(view.root,n=>n.tag==='a'&&text(n)==='Scan selected devices');
  assert.match(link.props.href,/operation=system.scan/);assert.match(link.props.href,/devices=1,2/);
  assert.equal(mutations(view).length,0);
  assert.equal(view.calls.filter(c=>c.url.endsWith('/inspect')).length,1);
 } finally {view.app.unmount();}
});

const inspections=view=>view.calls.filter(c=>c.url.endsWith('/inspect'));

test('Accounts opens first and hides absent, unverified, and excluded accounts',async()=>{
 const v=await mount({initialMode:'accounts',stale:true,accountsAfter:[
  {id:1,username:'jane',placements:[{device_id:1,state:'absent'}]},
  {id:2,username:'unverified',placements:[{device_id:1,state:'unverified'}]},
  {id:3,username:'actual',placements:[{device_id:1,state:'observed',full_name:'Actual Node Name',uid:1002,home:'/home/actual',groups:'actual,sudo',shell:'/bin/sh',managed_sudo:false,sudo_policy:'(ALL : ALL) ALL'}]},
  {id:4,username:'root',placements:[{device_id:1,state:'observed',uid:0,groups:'root',shell:'/bin/bash'}]},
  {id:5,username:'_apt',placements:[{device_id:1,state:'not_in_scope',uid:42}]},
 ]});try{
  assert.equal(inspections(v).length,1);assert.deepEqual(inspections(v)[0].body.device_ids,[1]);
  assert.equal(find(v.root,n=>n.tag==='button'&&text(n)==='Accounts').props['aria-pressed'],true);
  assert.match(text(v.root),/Actual Node Name/);assert.match(text(v.root),/UID 1002/);assert.match(text(v.root),/actual,sudo/);assert.match(text(v.root),/\(ALL : ALL\) ALL/);
  assert.ok(!find(v.root,n=>n.props['aria-label']==='Select jane'));assert.ok(!find(v.root,n=>n.props['aria-label']==='Select unverified'));
  assert.ok(!find(v.root,n=>n.props['aria-label']==='Select _apt'));
  assert.equal(find(v.root,n=>n.props['aria-label']==='Select root').props.disabled,true);
  assert.equal(mutations(v).length,0);assert.match(text(v.root),/Accounts refreshed/);
 }finally{v.app.unmount();}
});

test('selecting devices and returning to Accounts refreshes exactly the current scope',async()=>{
 const v=await mount({initialMode:'accounts',query:{}});try{
  assert.equal(inspections(v).length,0);assert.match(text(v.root),/Select devices to view/);
  const device=find(v.root,n=>n.tag==='input'&&n.props.type==='checkbox'&&n.props.value===2);
  device.props['onUpdate:modelValue']([2]);await flush();
  assert.deepEqual(inspections(v)[0].body.device_ids,[2]);
  await v.click('Add users');await v.click('Accounts');assert.equal(inspections(v).length,2);
  await v.click('Refresh');assert.equal(inspections(v).length,3);
  assert.ok(inspections(v).every(c=>JSON.stringify(c.body.device_ids)==='[2]'));
  assert.equal(new Set(inspections(v).map(c=>c.body.request_key)).size,3);
 }finally{v.app.unmount();}
});

test('account refresh reports pending and failed observations without claiming freshness',async()=>{
 for(const inspectState of ['running','failed']){
  const v=await mount({initialMode:'accounts',inspectState});try{
   assert.doesNotMatch(text(v.root),/Accounts refreshed/);
   if(inspectState==='running')assert.match(text(v.root),/Reading accounts from the selected devices/);
   else assert.match(text(v.root),/SSH connection failed/);
  }finally{v.app.unmount();}
 }
});

test('uncertain account discovery reconnects with the same scope and request key',async()=>{
 const v=await mount({initialMode:'accounts',inspectFailOnce:true});try{
  assert.match(text(v.root),/may have been accepted/);
  await v.click('Reconnect to request');assert.deepEqual(inspections(v)[0].body,inspections(v)[1].body);
  assert.match(text(v.root),/Accounts refreshed/);
 }finally{v.app.unmount();}
});

test('sudo checkbox is explicit, reviewed and supports a sudo-only edit',async()=>{
 for(const mode of ['add','edit']){
  const v=await mount({initialMode:mode});try{
   await v.input('Username row 1','jane');
   if(mode==='add')await v.input('Full name row 1','Jane');
   const box=find(v.root,n=>n.props['aria-label']==='Grant sudo access row 1');
   assert.equal(box.props.type,'checkbox');assert.equal(box.checked,false);
   await v.input('Grant sudo access row 1',true);await v.click(mode==='add'?'Review additions':'Review changes');
   assert.match(text(v.root),/Grant passwordless sudo/);assert.equal(mutations(v).length,0);
   await v.click(mode==='add'?'Add users now':'Apply changes');
   assert.equal(mutations(v)[0].body.users[0].grant_sudo,true);
  }finally{v.app.unmount();}
 }
});

test('unchecking sudo before submission does not request a privilege change',async()=>{
 const v=await mount({initialMode:'edit'});try{
  await v.input('Username row 1','jane');await v.input('Groups row 1','dev');
  await v.input('Grant sudo access row 1',true);await v.input('Grant sudo access row 1',false);
  await v.click('Review changes');await v.click('Apply changes');
  assert.deepEqual(mutations(v)[0].body.users,[{username:'jane',groups:'dev'}]);
 }finally{v.app.unmount();}
});


test('reopening a completed job refreshes accounts while an active job resumes polling',async()=>{
 for(const state of ['success','running']){
  const v=await mount({initialMode:'accounts',query:{devices:'1',job:'user-job'},jobState:state});try{
   assert.equal(inspections(v).length,state==='success'?1:0);
   assert.ok(v.calls.some(c=>c.url==='/api/v2/jobs/user-job/progress'));
   assert.equal(v.calls.some(c=>c.url==='/api/v2/jobs/user-job'),state==='success');
  }finally{v.app.unmount();}
 }
});


test('Accounts discovers the full inventory when a resumed account change completes',async()=>{
 const v=await mount({initialMode:'accounts',query:{devices:'1',job:'user-job'},jobState:['running','success']});try{
  assert.equal(inspections(v).length,0);
  await new Promise(resolve=>setTimeout(resolve,2100));await flush();
  assert.equal(inspections(v).length,1);assert.match(text(v.root),/Accounts refreshed/);
 }finally{v.app.unmount();}
});

test('reopening an old account inspection starts a fresh read',async()=>{
 const v=await mount({initialMode:'accounts',query:{devices:'1',job:'inspect-job'}});try{
  assert.equal(inspections(v).length,1);
 }finally{v.app.unmount();}
});

test('a failed account change remains visible without an automatic inspection replacing it',async()=>{
 const v=await mount({initialMode:'accounts',query:{devices:'1',job:'user-job'},jobState:'partial'});try{
  assert.equal(inspections(v).length,0);assert.match(text(v.root),/Some devices need attention/);
 }finally{v.app.unmount();}
});
