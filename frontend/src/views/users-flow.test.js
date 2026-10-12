import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {parse,compileScript} from '@vue/compiler-sfc';
import {createRenderer,nextTick} from 'vue';
import {createRouter,createMemoryHistory} from 'vue-router';

function element(tag,text='') { return {tag,text,props:{},children:[],parent:null,get options(){return this.children.filter(c=>c.tag==='option');},get value(){return this.props.value;},set value(v){this.props.value=v;},getRootNode(){return {activeElement:null};},focus(){},scrollIntoView(){},addEventListener(){},removeEventListener(){},setAttribute(){},removeAttribute(){}}; }
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
const {default:Users}=await import(await compileView(new URL('./UserManagement.vue',import.meta.url)));
const devices=[{id:1,name:'Node 1',inventory_name:'node-01',discovered_at:new Date().toISOString(),transport:'ssh',capabilities:['users.manage'],os_family:'Debian',facts_stale:false,recovery_required:true},{id:2,name:'Node 2',inventory_name:'node-02',discovered_at:new Date().toISOString(),transport:'ssh',capabilities:['users.manage']}];
async function mount({query={devices:'1'},failOnce=false,csvError=false,jobState='success',stale=false}={}) {
 global.Document=class Document {};global.ShadowRoot=class ShadowRoot {};global.document={activeElement:null};global.localStorage={getItem:()=> 'test'};global.window={location:{hash:''}};
 const calls=[];let posted=0;
 global.fetch=async(url,options={})=>{
  const body=options.body instanceof FormData ? options.body : options.body?JSON.parse(options.body):null;
  calls.push({url,options,body});
  const respond=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
  if(url==='/api/v2/devices')return respond(devices.map(d=>({...d,facts_stale:stale})));
  if(url==='/api/v2/users')return respond([{id:1,username:'jane',full_name:'Jane',placements:[{device_id:1,state:'observed',groups:'users',shell:'/bin/bash'}]}]);
  if(url==='/api/v2/users/csv-preview')return csvError?respond({detail:'Row 3: duplicate username jane'},400):respond({users:body.get('mode')==='edit'?[{username:'jane',groups:'dev,docker',shell:'/bin/bash'},{username:'sam',full_name:'Sam Updated'}]:[{username:'jane',full_name:'Doe, Jane',email:'jane@example.com'},{username:'sam',full_name:'Sam'}]});
  if(options.method==='POST'||options.method==='PUT'){
   posted++;if(failOnce&&posted===1)throw new Error('Connection lost');
   return respond({job_id:'user-job'});
  }
  if(url==='/api/v2/jobs/user-job')return respond({job_id:'user-job',playbook:'user_management.yml',status:jobState,phase:jobState==='running'?'checking_health':'complete',device_results:[{hostname:'node-01',status:jobState,detail:jobState==='partial'?'Account sam does not exist':undefined}],result_artifacts:[]});
  throw new Error(`Unexpected request ${url}`);
 };
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/access',component:Users},{path:'/:pathMatch(.*)*',component:{render:()=>null}}]});
 await router.push({path:'/access',query});await router.isReady();
 const app=renderer.createApp(Users).use(router),root=element('root');app.mount(root);await flush();
 const click=async label=>{const b=find(root,n=>n.tag==='button'&&text(n)===label);assert.ok(b,`Missing ${label}`);assert.ok(!b.props.disabled,`${label} disabled`);await b.props.onClick();await flush();};
 const input=async(label,value)=>{const el=find(root,n=>n.props['aria-label']===label);assert.ok(el,`Missing ${label}`);el.props['onUpdate:modelValue'](value);await flush();};
 const upload=async()=>{const file=find(root,n=>n.tag==='input'&&n.props.type==='file');await file.props.onChange({target:{files:[new File(['test'],'users.csv',{type:'text/csv'})],value:'users.csv'}});await flush();};
 return{app,root,calls,router,click,input,upload};
}
const mutations=view=>view.calls.filter(c=>['POST','PUT'].includes(c.options.method)&&!c.url.endsWith('csv-preview'));

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
  assert.equal(view.calls.filter(c=>c.options.method==='POST').length,0);
 } finally {view.app.unmount();}
});
