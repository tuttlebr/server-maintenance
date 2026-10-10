<template>
  <div class="user-management">
    <header class="page-header"><div><h2>Users</h2><p class="muted">Add and edit Linux accounts across your devices.</p></div><button class="btn btn-ghost btn-sm" :disabled="locked || loading" @click="load">Refresh</button></header>
    <p v-if="loadError" class="callout callout-danger" role="alert">{{ loadError }} <button class="btn btn-ghost btn-sm" :disabled="locked" @click="load">Try again</button></p>
    <p v-if="loading && !devices.length" role="status">Loading users and devices…</p>
    <div v-else class="workspace">
      <aside class="card devices-panel" aria-labelledby="users-device-heading">
        <h3 id="users-device-heading">Target devices</h3><p aria-live="polite" class="muted">{{ selectedIds.length }} selected</p>
        <label class="visually-hidden" for="users-device-search">Find a device</label><input id="users-device-search" v-model="deviceSearch" class="form-input" type="search" placeholder="Find a device…" />
        <div class="selection-tools"><button class="text-button" :disabled="locked || !!pending" @click="selectVisible">Select visible</button><button class="text-button" :disabled="locked || !!pending" @click="selectedIds = []">Clear</button></div>
        <label v-for="device in visibleDevices" :key="device.id" :class="['device-option',{selected:selectedIds.includes(device.id)}]"><input v-model="selectedIds" type="checkbox" :value="device.id" :disabled="locked || !!pending" /><span><strong>{{ device.name }}</strong><small>{{ device.os_version || device.os_family || 'Platform checked automatically' }}</small><small v-if="device.recovery_required" class="warning-text">Health checked before changes</small></span></label>
        <p v-if="!devices.length" class="muted">No SSH devices available. <router-link to="/devices?add=1">Add a device</router-link></p><p v-else-if="!visibleDevices.length" class="muted">No matching devices.</p>
        <p v-if="missingIds.length" class="callout callout-warn" role="alert">Unavailable devices: {{ missingIds.join(', ') }}. <button class="text-button" :disabled="locked || !!pending" @click="selectedIds = selectedIds.filter(id => devices.some(d => d.id === id))">Remove unavailable devices</button></p>
        <p class="scope-note">Every row applies to every selected device. Debian and Red Hat family Linux supported. No node draining.</p>
      </aside>
      <main class="main-panel">
        <div class="tabs" aria-label="User management mode"><button v-for="item in modes" :key="item.id" :class="['tab',{active:mode === item.id}]" :aria-pressed="mode === item.id" :disabled="locked || !!pending" @click="changeMode(item.id)">{{ item.label }}</button></div>
        <section v-if="!pending && mode !== 'accounts'" class="card editor" aria-labelledby="editor-heading">
          <h3 id="editor-heading">{{ mode === 'add' ? 'Add users' : 'Edit users' }}</h3>
          <p class="muted">{{ mode === 'add' ? 'Create missing accounts. Existing accounts are kept as they are. Email is optional when you supply a username.' : 'Enter usernames and only the fields you want to change. Blank fields stay unchanged. Groups are appended without removing existing memberships.' }} Email is stored in Fleet Manager.</p>
          <fieldset :disabled="locked" class="editor-fields">
            <CsvUpload :key="mode" :mode="mode" :disabled="locked" @parsed="importRows" @busy="importing = $event" />
            <div class="table-wrapper"><table class="edit-table"><thead><tr><th scope="col">Username</th><th scope="col">Full name{{ mode === 'add' ? ' *' : '' }}</th><th scope="col">Email</th><th scope="col">Append groups</th><th scope="col">Login shell</th><th scope="col"><span class="visually-hidden">Remove</span></th></tr></thead><tbody><tr v-for="(row,index) in rows" :key="index">
              <td data-label="Username"><input v-model="row.username" class="form-input" :aria-label="`Username row ${index+1}`" :placeholder="mode === 'add' ? 'From email, or enter' : 'username'" autocomplete="off" autocapitalize="none" spellcheck="false" /></td>
              <td data-label="Full name"><input v-model="row.full_name" class="form-input" :aria-label="`Full name row ${index+1}`" :placeholder="mode === 'add' ? 'Full name' : 'Keep current'" /></td>
              <td data-label="Email"><input v-model="row.email" type="email" class="form-input" :aria-label="`Email row ${index+1}`" :placeholder="mode === 'add' ? 'Optional' : 'Keep current'" /></td>
              <td data-label="Append groups"><input v-model="row.groups" class="form-input" :aria-label="`Groups row ${index+1}`" placeholder="developers,docker" /></td>
              <td data-label="Login shell"><select v-model="row.shell" class="form-select" :aria-label="`Shell row ${index+1}`"><option value="">{{ mode === 'add' ? 'Default: /bin/bash' : 'Keep current' }}</option><option v-for="shell in SHELLS" :key="shell">{{ shell }}</option></select></td>
              <td><button class="btn btn-ghost btn-sm" :aria-label="`Remove row ${index+1}`" :disabled="rows.length === 1" @click="rows.splice(index,1)"><i class="fas fa-xmark" aria-hidden="true"></i></button></td>
            </tr></tbody></table></div>
            <div class="row-tools"><button class="btn btn-ghost btn-sm" :disabled="rows.length >= 500" @click="rows.push(blankUser())">Add row</button><span class="muted">{{ rows.length }} / 500 rows</span></div>
            <details v-if="rows.length > 1" class="shared-edits"><summary>Apply groups or shell to every row</summary><div class="shared-fields"><label>Append groups<input v-model="sharedGroups" class="form-input" placeholder="developers,docker" /></label><label>Login shell<select v-model="sharedShell" class="form-select"><option value="">No shared change</option><option v-for="shell in SHELLS" :key="shell">{{ shell }}</option></select></label><button class="btn btn-ghost" :disabled="!sharedGroups && !sharedShell" @click="applyShared">Apply to rows</button></div></details>
            <details v-if="mode === 'add'" class="initial-password"><summary>Set an initial password (optional)</summary><label class="form-label" for="initial-password">Initial password for new accounts</label><input id="initial-password" v-model="password" class="form-input" type="password" autocomplete="new-password" minlength="12" /><p class="muted">At least 12 characters. A password change is required at first login. Without a password, new accounts have password login locked.</p></details>
          </fieldset>
          <div v-if="validationErrors.length" class="callout callout-danger" role="alert"><p v-for="error in validationErrors" :key="error">{{ error }}</p></div>
          <div class="editor-footer"><p class="muted">{{ selectedIds.length ? `${selectedIds.length} selected devices` : 'Select target devices to continue.' }}</p><button class="btn btn-primary" :disabled="locked || loading || !!loadError || !selectedIds.length || !!missingIds.length" @click="review">Review {{ mode === 'add' ? 'additions' : 'changes' }}</button></div>
        </section>
        <section v-else-if="!pending" class="card accounts-panel">
          <div class="accounts-toolbar"><input v-model="accountSearch" class="form-input" aria-label="Search users" type="search" placeholder="Search users…" /><button class="btn btn-ghost btn-sm" :disabled="locked || loading || !!loadError || !selectedIds.length || !!missingIds.length" @click="inspect">Refresh accounts</button><button class="btn btn-primary btn-sm" :disabled="locked || !selectedUsers.length" @click="editSelected">Edit {{ selectedUsers.length || 'selected' }} users</button></div>
          <p class="muted">Account state from the last observation on your selected devices. Refresh accounts to discover existing users.</p>
          <div class="table-wrapper"><table><thead><tr><th><input type="checkbox" :checked="allVisibleSelected" :disabled="locked || !filteredUsers.length" aria-label="Select all visible users" @change="selectUsers($event.target.checked)" /></th><th>User</th><th>State on selected devices</th></tr></thead><tbody><tr v-for="user in filteredUsers" :key="user.id"><td><input v-model="selectedUsers" type="checkbox" :value="user.username" :disabled="locked" :aria-label="`Select ${user.username}`" /></td><td><strong>{{ user.username }}</strong><small>{{ user.full_name }}</small><small>{{ user.email }}</small></td><td><div v-for="device in selectedDevices" :key="device.id" class="placement"><strong>{{ device.name }}</strong><template v-if="accountPlacement(user,device.id).state === 'observed'"><span>{{ accountPlacement(user,device.id).groups || 'No supplementary groups' }} · {{ accountPlacement(user,device.id).shell }}</span><small>Observed {{ formatLongTime(accountPlacement(user,device.id).observed_at) }}</small></template><span v-else>{{ accountPlacement(user,device.id).state === 'absent' ? 'Account absent' : 'Not yet observed' }}</span></div></td></tr></tbody></table></div>
          <p v-if="!selectedIds.length" class="empty-state">Select devices to view their accounts.</p><p v-else-if="!filteredUsers.length" class="empty-state">No matching accounts. Refresh accounts to discover them, or add users.</p>
        </section>
        <section v-if="pending" ref="reviewPanel" class="card review-panel" tabindex="-1" aria-labelledby="user-review-heading">
          <span class="eyebrow">Review and run</span><h3 id="user-review-heading">{{ pending.mode === 'add' ? 'Add' : 'Edit' }} {{ pending.payload.users.length }} {{ pending.payload.users.length === 1 ? 'user' : 'users' }} on {{ pending.devices.length }} {{ pending.devices.length === 1 ? 'device' : 'devices' }}?</h3><p class="targets">{{ pending.devices.map(d => d.name).join(', ') }}</p>
          <p class="muted">{{ pending.mode === 'add' ? 'Existing accounts remain unchanged. New accounts use system home directory defaults.' : 'Only these fields change. Existing group memberships and home directories are preserved.' }}</p><p v-if="pending.devices.some(d => d.recovery_required)" class="muted">Pending health checks run automatically before account changes.</p>
          <div class="table-wrapper"><table class="review-table"><thead><tr><th>Username</th><th>Full name</th><th>Email</th><th>Append groups</th><th>Login shell</th></tr></thead><tbody><tr v-for="row in pending.payload.users" :key="row.username"><td data-label="Username"><strong>{{ row.username }}</strong></td><td data-label="Full name">{{ row.full_name || 'Keep current' }}</td><td data-label="Email">{{ row.email || (pending.mode === 'add' ? 'None' : 'Keep current') }}</td><td data-label="Append groups">{{ row.groups || (pending.mode === 'add' ? 'Default' : 'Keep current') }}</td><td data-label="Login shell">{{ row.shell || (pending.mode === 'add' ? '/bin/bash' : 'Keep current') }}</td></tr></tbody></table></div>
          <p v-if="pending.mode === 'add'" class="muted">{{ pending.payload.password ? 'Initial password set. New users must change it at first login.' : 'New accounts have password login locked.' }}</p>
          <div class="review-actions"><button class="btn btn-primary" :disabled="starting" @click="submit">{{ starting ? 'Starting…' : uncertain ? 'Reconnect to request' : pending.mode === 'add' ? 'Add users now' : 'Apply changes' }}</button><button class="btn btn-ghost" :disabled="starting || uncertain" @click="pending = null; actionError = ''">Back to editing</button></div>
        </section>
        <div v-if="actionError" class="callout callout-danger action-error" role="alert">{{ actionError }}<p v-if="uncertain">The request may have been accepted. Reconnect to the same request to avoid applying it twice.</p><button v-if="uncertain && !pending" class="btn btn-ghost btn-sm" :disabled="starting" @click="inspect">Reconnect to request</button></div>
        <section v-if="job" class="card job-panel" aria-labelledby="user-job-heading">
          <div class="job-heading"><h3 id="user-job-heading">{{ jobHeadline }}</h3><StatusBadge :status="job.status" /></div>
          <p v-if="jobActive" role="status" class="muted">{{ progressMessage }}</p><p v-if="job.error_summary" class="warning-text">{{ job.error_summary }}</p>
          <p v-if="pollError" class="callout callout-warn" role="alert">{{ pollError }} <button class="text-button" @click="pollJob(job.job_id)">Reconnect</button></p>
          <div v-for="outcome in job.device_results || []" :key="outcome.hostname" class="outcome"><strong>{{ devices.find(d => d.inventory_name === outcome.hostname)?.name || outcome.hostname }}</strong><span>{{ statusLabel(outcome.status) }}</span><p v-if="outcome.detail">{{ outcome.detail }}</p></div>
          <div v-for="report in (job.result_artifacts || []).filter(r => r.report_type === 'accounts')" :key="report.hostname" class="account-result"><strong>{{ report.hostname }}</strong><p>{{ report.accounts.filter(a => a.present).length }} accounts observed after the operation.</p></div>
          <router-link :to="{path:'/activity',query:{job:job.job_id}}">View full activity</router-link><details v-if="job.output_log" class="technical-log"><summary>Technical log</summary><pre>{{ job.output_log }}</pre></details>
        </section>
      </main>
    </div>
  </div>
</template>
<script setup>
import {computed,nextTick,onMounted,onUnmounted,ref} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import {getDevices,getUsers,bulkAddUsers,bulkUpdateUsers,inspectAccounts,getJob} from '../api.js';
import CsvUpload from '../components/CsvUpload.vue';
import StatusBadge from '../components/StatusBadge.vue';
import {accountPlacement} from '../utils/access.js';
import {parseDeviceIds} from '../utils/fleetOverview.js';
import {formatLongTime} from '../utils/time.js';
import {ACTIVE,statusLabel} from '../utils/maintenance.js';
import {SHELLS,blankUser,validateUserRows} from '../utils/users.js';
const route=useRoute(),router=useRouter();
const modes=[{id:'add',label:'Add users'},{id:'edit',label:'Edit users'},{id:'accounts',label:'Accounts'}];
const mode=ref('add'),drafts=ref({add:[blankUser()],edit:[blankUser()]}),devices=ref([]),users=ref([]),selectedIds=ref(parseDeviceIds(route.query.devices || route.query.device)),selectedUsers=ref([]);
const rows=computed({get:()=>drafts.value[mode.value === 'accounts' ? 'edit' : mode.value],set:value=>{drafts.value[mode.value === 'accounts' ? 'edit' : mode.value]=value;}});
const deviceSearch=ref(''),accountSearch=ref(''),password=ref(''),sharedGroups=ref(''),sharedShell=ref('');
const loading=ref(true),loadError=ref(''),starting=ref(false),importing=ref(false),pending=ref(null),uncertain=ref(false),actionError=ref(''),validationErrors=ref([]),reviewPanel=ref(null);
const job=ref(null),pollError=ref('');
let disposed=false,timer,inspectionRequest=null;
const jobActive=computed(()=>job.value && ACTIVE.includes(job.value.status));
const locked=computed(()=>starting.value || importing.value || jobActive.value || uncertain.value);
const selectedDevices=computed(()=>devices.value.filter(d=>selectedIds.value.includes(d.id)));
const visibleDevices=computed(()=>devices.value.filter(d=>`${d.name} ${d.inventory_name}`.toLowerCase().includes(deviceSearch.value.toLowerCase())));
const missingIds=computed(()=>selectedIds.value.filter(id=>!devices.value.some(d=>d.id===id)));
const filteredUsers=computed(()=>users.value.filter(u=>(u.placements || []).some(p=>selectedIds.value.includes(p.device_id)) && `${u.username} ${u.full_name || ''} ${u.email || ''}`.toLowerCase().includes(accountSearch.value.toLowerCase())));
const allVisibleSelected=computed(()=>filteredUsers.value.length>0 && filteredUsers.value.every(u=>selectedUsers.value.includes(u.username)));
const jobHeadline=computed(()=>jobActive.value ? 'Account operation in progress' : job.value?.status==='success' ? job.value.playbook==='access_inspect.yml' ? 'Accounts refreshed' : 'Account changes completed' : job.value?.status==='partial' ? 'Some devices need attention' : 'Account operation needs attention');
const progressMessage=computed(()=>({checking_health:'Checking device health before making changes…',checking_facts:'Refreshing device details before continuing…',refreshing_facts:'Account changes finished. Refreshing device details…'})[job.value?.phase] || 'Working on the selected devices. Progress is also available in Activity.');
async function load(){loading.value=true;loadError.value='';try{const [d,u]=await Promise.all([getDevices(),getUsers()]);if(disposed)return;devices.value=d.filter(d=>d.transport==='ssh' && d.capabilities.includes('users.manage'));users.value=u;}catch(e){loadError.value=`Could not load user management. ${e.message}`;}finally{loading.value=false;}}
function selectVisible(){selectedIds.value=[...new Set([...selectedIds.value,...visibleDevices.value.map(d=>d.id)])];}
function changeMode(next){mode.value=next;validationErrors.value=[];sharedGroups.value='';sharedShell.value='';}
function importRows(records){rows.value=records.map(record=>({...blankUser(),...record}));validationErrors.value=[];}
function applyShared(){rows.value=rows.value.map(row=>({...row,...(sharedGroups.value.trim()?{groups:sharedGroups.value.trim()}:{}),...(sharedShell.value?{shell:sharedShell.value}:{})}));}
function selectUsers(checked){selectedUsers.value=checked ? [...new Set([...selectedUsers.value,...filteredUsers.value.map(u=>u.username)])] : selectedUsers.value.filter(name=>!filteredUsers.value.some(u=>u.username===name));}
function editSelected(){const names=[...selectedUsers.value];changeMode('edit');rows.value=names.map(blankUser);}
async function review(){
  if(locked.value || loading.value || loadError.value || !selectedIds.value.length || missingIds.value.length)return;
  const checked=validateUserRows(rows.value,mode.value);validationErrors.value=checked.errors;
  if(mode.value==='add' && password.value && password.value.length<12)validationErrors.value.push('Initial password must be at least 12 characters.');
  if(validationErrors.value.length)return;
  actionError.value='';
  pending.value={mode:mode.value,devices:selectedDevices.value.map(d=>({...d})),payload:{device_ids:[...selectedIds.value],users:checked.users,request_key:crypto.randomUUID(),...(mode.value==='add' && password.value ? {password:password.value}: {})}};
  await nextTick();reviewPanel.value?.focus({preventScroll:true});reviewPanel.value?.scrollIntoView({behavior:'smooth',block:'nearest'});
}
async function accept(result){
  uncertain.value=false;inspectionRequest=null;password.value='';pending.value=null;
  job.value={job_id:result.job_id,status:'pending',device_results:[],playbook:'user_management.yml'};
  // Keep accepted work visible even if URL navigation or polling fails.
  try{await router.replace({path:'/access',query:{devices:selectedIds.value.join(','),job:result.job_id}});}catch{}
  await pollJob(result.job_id);
}
async function submit(){
  if(starting.value || !pending.value)return;
  starting.value=true;actionError.value='';
  try{const p=pending.value;const result=await (p.mode==='add'?bulkAddUsers(p.payload):bulkUpdateUsers(p.payload));await accept(result);}
  catch(e){actionError.value=e.message;uncertain.value=!e.status || e.status>=500;}
  finally{starting.value=false;}
}
async function inspect(){
  if(starting.value || jobActive.value || importing.value || loading.value || !!loadError.value || !selectedIds.value.length || missingIds.value.length)return;
  starting.value=true;actionError.value='';
  inspectionRequest ||= {device_ids:[...selectedIds.value],request_key:crypto.randomUUID()};
  try{await accept(await inspectAccounts(inspectionRequest));}
  catch(e){actionError.value=e.message;uncertain.value=!e.status || e.status>=500;if(!uncertain.value)inspectionRequest=null;}
  finally{starting.value=false;}
}
async function pollJob(id){
  clearTimeout(timer);pollError.value='';
  try{const result=await getJob(id);if(disposed || job.value?.job_id!==id)return;job.value=result;if(ACTIVE.includes(result.status))timer=setTimeout(()=>pollJob(id),2000);else await load();}
  catch(e){if(!disposed)pollError.value=`Could not refresh progress. ${e.message}`;}
}
onMounted(async()=>{await load();if(route.query.job){job.value={job_id:route.query.job,status:'pending',device_results:[]};await pollJob(route.query.job);}});
onUnmounted(()=>{disposed=true;clearTimeout(timer);password.value='';pending.value=null;});
</script>
<style scoped>
.table-wrapper{position:relative}.muted,small{color:var(--text-secondary)}.muted{line-height:1.6}.workspace{display:grid;grid-template-columns:240px minmax(0,1fr);gap:20px;align-items:start}.devices-panel{padding:20px}.devices-panel>p{font-size:13px;margin:8px 0 16px}.selection-tools{display:flex;gap:14px;margin:12px 0}.text-button{border:0;background:none;color:var(--link-text);padding:0;font:inherit;font-size:12px;cursor:pointer}.text-button:disabled{opacity:.5;cursor:default}.device-option{display:flex;gap:10px;align-items:start;padding:12px 8px;border-top:1px solid var(--border-subtle);cursor:pointer}.device-option.selected{background:var(--surface-light)}.device-option input{margin-top:4px}.device-option strong{font-size:13px}.device-option span{min-width:0;overflow-wrap:anywhere}small{display:block;font-size:12px;margin-top:4px}.scope-note{line-height:1.5}.main-panel{min-width:0}.tabs{margin-bottom:16px}.editor,.accounts-panel,.review-panel,.job-panel{padding:22px}.editor>h3,.review-panel>h3{margin-bottom:10px}.editor>p,.review-panel>p{font-size:13px}.editor-fields{padding:0;margin:0;border:0;min-width:0}.edit-table{min-width:760px}.edit-table th{font-size:11px}.edit-table td{padding:8px 5px}.edit-table .form-input,.edit-table .form-select{font-size:12px;min-width:115px}.edit-table td:last-child{width:36px}.row-tools,.editor-footer,.review-actions,.accounts-toolbar,.job-heading{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.row-tools{justify-content:space-between;margin:10px 0}.row-tools span{font-size:12px}.editor-footer{justify-content:space-between;margin-top:20px}.editor-footer p{font-size:13px}.initial-password,.shared-edits{border-top:1px solid var(--border-subtle);padding:14px 0}.initial-password input{max-width:360px}.initial-password .form-label{margin-top:14px}.initial-password p{font-size:12px}.shared-fields{display:flex;flex-wrap:wrap;align-items:end;gap:12px;margin-top:12px}.shared-fields label{font-size:12px;flex:1;min-width:150px}.shared-fields input,.shared-fields select{margin-top:6px}summary{cursor:pointer;font-size:13px}.eyebrow{display:block;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-secondary);margin-bottom:8px}.targets{font-weight:600;overflow-wrap:anywhere}.review-actions{margin-top:20px}.accounts-toolbar input{flex:1;min-width:160px}.accounts-panel>p{font-size:13px;margin:14px 0}.placement{display:grid;gap:3px;padding:8px 0;border-bottom:1px solid var(--border-subtle);font-size:12px}.job-panel{margin-top:20px}.job-heading{justify-content:space-between;margin-bottom:12px}.job-panel>p,.outcome,.account-result{font-size:13px}.outcome{display:grid;grid-template-columns:1fr auto;gap:8px;padding:12px 0;border-bottom:1px solid var(--border-subtle)}.outcome p{grid-column:1/-1;color:var(--danger-text);margin:0}.account-result{padding:12px 0}.job-panel>a{display:inline-block;margin-top:14px}.technical-log{margin-top:16px}.technical-log pre{max-height:320px;overflow:auto;white-space:pre-wrap;font-size:12px}.warning-text{color:var(--warning-text)}.action-error{white-space:pre-wrap;margin-top:16px}.callout p{margin:4px 0}.empty-state{padding:20px}
@media(max-width:1000px){.workspace{grid-template-columns:200px minmax(0,1fr);gap:14px}.editor,.accounts-panel,.review-panel,.job-panel{padding:16px}}@media(max-width:760px){.workspace{grid-template-columns:1fr}.devices-panel{padding:16px}.device-option{display:inline-flex;vertical-align:top;min-width:180px;width:50%}.editor-footer .btn{width:100%}.review-actions .btn{flex:1}.devices-panel .device-option{width:100%;min-width:0}.tabs .tab{padding:12px 16px;flex:1}.edit-table{min-width:0}.edit-table thead{display:none}.edit-table,.edit-table tbody{display:block}.edit-table tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:12px;border-bottom:1px solid var(--border-subtle)}.edit-table td{display:block;padding:0;border:0}.edit-table td::before{content:attr(data-label);display:block;font-size:11px;color:var(--text-secondary);margin-bottom:5px}.edit-table td:nth-child(3){grid-column:1/-1}.edit-table td:last-child{width:auto;grid-column:1/-1;text-align:right}.edit-table .form-input,.edit-table .form-select{min-width:0;width:100%}.review-table thead{display:none}.review-table,.review-table tbody{display:block}.review-table tr{display:grid;gap:10px;padding:14px;border-bottom:1px solid var(--border-subtle)}.review-table td{display:grid;grid-template-columns:90px minmax(0,1fr);gap:10px;border:0;padding:0;font-size:13px;overflow-wrap:anywhere}.review-table td::before{content:attr(data-label);color:var(--text-secondary);font-size:12px}}
</style>
