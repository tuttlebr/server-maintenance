// Design-review harness. Serves the existing Vue app with synthetic API data.
// No production API proxy, credentials, SSH, or machine operations.
import { createServer } from 'vite';
import vue from '@vitejs/plugin-vue';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const now = Date.now();
const ago = minutes => new Date(now - minutes * 60000).toISOString();
const base = (id, name, extra = {}) => ({ id, name, inventory_name: name, endpoint: `192.0.2.${id}`, kind: 'server', transport: 'ssh', vendor: 'Generic', model: 'Linux compute', status: 'online', architecture: 'x86_64', os_version: 'Ubuntu 24.04', os_family: 'Debian', memory_gb: 64, disk_root_percent: 42, reboot_required: false, recovery_required: false, facts_stale: false, maintenance_mode: 'standalone', capabilities: ['system.scan', 'system.reboot', 'storage.inspect', 'users.manage'], last_seen: ago(12), discovered_at: ago(12), facts: {}, annotations: {}, ...extra });
const devices = [
 base(1,'atlas-01',{disk_root_percent:94,reboot_required:true,facts_stale:true}),
 base(2,'atlas-02',{status:'offline',facts_stale:true}),
 base(3,'edge-01',{kind:'edge',model:'Edge gateway',status:'offline',facts_stale:true}),
 base(4,'edge-02',{kind:'edge',model:'Edge gateway'}),
 base(5,'gpu-01',{vendor:'NVIDIA',model:'DGX Spark',gpu_model:'GB10',memory_gb:128,architecture:'aarch64',capabilities:['system.scan','gpu.inspect','storage.inspect','users.manage']}),
 base(6,'gpu-02',{vendor:'NVIDIA',model:'DGX Workstation',kind:'workstation',gpu_model:'RTX PRO 6000',disk_root_percent:88,reboot_required:true,capabilities:['system.scan','gpu.inspect','storage.inspect','users.manage']}),
 base(7,'new-node',{status:'unknown',last_seen:null,discovered_at:null,disk_root_percent:null,capabilities:[]}),
 base(8,'robot-01',{kind:'robot',transport:'reachy_daemon',vendor:'Pollen Robotics',model:'Reachy Mini Wireless',capabilities:['reachy.health'],disk_root_percent:null,memory_gb:null}),
 base(9,'robot-02',{kind:'robot',transport:'reachy_daemon',vendor:'Pollen Robotics',model:'Reachy Mini Wireless',status:'offline',capabilities:['reachy.health'],disk_root_percent:null,memory_gb:null}),
 base(10,'storage-01'),base(11,'worker-01'),
 base(12,'worker-02',{recovery_required:true,recovery_reason:'Maintenance interrupted; verify remote state before continuing.',facts_stale:true,maintenance_mode:'kubernetes',facts:{kubernetes_unschedulable:true,kubernetes_available:true}})
];
const jobs = [
 ['host_facts.yml','running','atlas-01,atlas-02',2],['storage_analysis.yml','pending','gpu-02',4],
 ['host_facts.yml','success','edge-02',8],['reachy.health','success','robot-01',11],
 ['gpu_usage.yml','success','gpu-01',16],['package_preview.yml','success','worker-01',20],
 ['system_update.yml','recovery_required','worker-02',28],['driver_upgrade.yml','failed','gpu-02',35],
 ['host_facts.yml','failed','atlas-02',45],['host_facts.yml','success','storage-01',55],
].map(([playbook,status,target_devices,age], i)=>({job_id:`review-job-${i+1}`,playbook,status,target_devices,created_at:ago(age),started_at:status==='pending'?null:ago(age),finished_at:['running','pending'].includes(status)?null:ago(age-1),duration_seconds:status==='pending'?null:60,triggered_by:'review-operator',phase:status==='running'?'scanning':'finished',error_summary:status==='failed'?'Connection failed before the operation completed.':status==='recovery_required'?'Maintenance interrupted; remote state needs verification.':null,device_results:target_devices.split(',').map(hostname=>({hostname,status:status==='success'?'success':status})),result_artifacts:[],output_log:`PLAY [${playbook}]\nTASK [Verify device state]\n${status==='failed'?'fatal':'ok'}: [${target_devices.split(',')[0]}]\nPLAY RECAP\n${target_devices.split(',')[0]} : ok=4 changed=0 unreachable=${status==='failed'?1:0} failed=0`,recap:''}));
const op=(id,label,description,risk,ids,excluded=[])=>({id,label,description,risk,category:risk==='high'?'Maintenance':'Inspect and verify',icon:risk==='high'?'fa-power-off':'fa-magnifying-glass',confirmation:risk==='high'?'typed-target':'simple',eligible_device_ids:ids,excluded_devices:excluded});
const operations=[op('system.scan','Scan devices','Refresh facts and discovered capabilities.','low',[1,4,5,6,7,10,11]),op('storage.inspect','Analyze storage','Inspect storage use before planning cleanup.','low',[1,4,5,6,10,11]),op('system.recover','Verify recovery','Verify remote state after interrupted maintenance.','low',[12]),op('system.reboot','Reboot devices','Restart selected devices. Running workloads may be interrupted.','high',[4,5,6,10,11],[{id:12,name:'worker-02',reason:'Recovery verification required'},{id:1,name:'atlas-01',reason:'Facts are stale'}])];
const server=await createServer({root:resolve(here,'..'),configFile:false,plugins:[vue(),{
 name:'design-review-fixtures',
 transformIndexHtml(html){return html.replace('<head>','<head><script>localStorage.setItem("fleet_token","design-review-only"); const p=new URLSearchParams(location.search); if(p.has("theme"))document.documentElement.dataset.theme=p.get("theme");</script>');},
 configureServer(v){v.middlewares.use((req,res,next)=>{
  if(!req.url.startsWith('/api/'))return next();
  const url=new URL(req.url,'http://127.0.0.1');
  const ref=new URL(req.headers.referer||'http://127.0.0.1');
  const scenario=ref.searchParams.get('scenario')||'mixed';
  const send=(data,code=200)=>{res.statusCode=code;res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));};
  if((scenario==='error' || (scenario==='jobs-error' && url.pathname.includes('/jobs'))) && !url.pathname.includes('chat'))return send({detail:'Synthetic API unavailable'},503);
  let ds=devices,js=jobs;
  if(scenario==='healthy'){ds=devices.filter(d=>d.id===4);js=[];}
  if(scenario==='empty'){ds=[];js=[];}
  if(scenario==='one'){ds=[base(1,'first-node',{status:'unknown',capabilities:[],last_seen:null,discovered_at:null,disk_root_percent:null})];js=[];}
  if(scenario==='five'){ds=devices.slice(0,5);js=jobs.filter(j=>j.target_devices.split(',').every(n=>ds.some(d=>d.inventory_name===n)));}
  if(scenario==='offline'){ds=devices.slice(0,5).map(d=>({...d,status:'offline'}));js=[];}
  if(scenario==='reachable'){ds=devices.map(d=>({...d,status:'online'}));}
  if(scenario==='large'){js=[];ds=Array.from({length:200},(_,i)=>base(i+1,`node-${String(i+1).padStart(3,'0')}`,i===199?{recovery_required:true}:{disk_root_percent:86}));}
  const path=url.pathname.replace('/api/v2','');
  if(req.method!=='GET')return send({detail:'Preview only. No operation was executed.'},409);
  if(path==='/devices')return send(ds);
  if(/^\/devices\/\d+$/.test(path))return send(ds.find(d=>d.id===Number(path.split('/').pop()))||{},ds.some(d=>d.id===Number(path.split('/').pop()))?200:404);
  if(path==='/jobs/summary')return send({active_count:js.filter(j=>['running','pending','cancelling'].includes(j.status)).length});
  if(path==='/jobs'){let filtered=js;const s=url.searchParams.get('status');if(s)filtered=filtered.filter(j=>s==='active'?['running','pending','cancelling'].includes(j.status):j.status===s);const p=url.searchParams.get('playbook');if(p)filtered=filtered.filter(j=>j.playbook===p);return send(filtered.slice(Number(url.searchParams.get('offset')||0),Number(url.searchParams.get('offset')||0)+Number(url.searchParams.get('limit')||50)));}
  if(path.endsWith('/stream')){res.setHeader('Content-Type','text/event-stream');return res.end('data: Synthetic preview: waiting for device\n\nevent: done\ndata: running\n\n');}
  if(path.startsWith('/jobs/'))return send(js.find(j=>j.job_id===path.split('/').pop())||{});
  if(path==='/operations')return send(ds.length?operations:[]);
  if(path==='/users'||path==='/context/documents')return send([]);
  if(path==='/chat/status')return send({available:false});
  if(path==='/context/status')return send({record_count:24,document_count:0,annotated_device_count:0,running:false,last_indexed_at:ago(90)});
  return send({detail:'No fixture for this endpoint'},404);
 });}
}],server:{host:'127.0.0.1',port:9012,strictPort:true}});
await server.listen();server.printUrls();
