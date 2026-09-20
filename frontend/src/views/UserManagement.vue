<template>
  <div>
    <div class="page-header"><div><h2>Access</h2><p class="muted">Select devices and accounts. Every change uses the scope shown in its confirmation.</p></div><button class="btn btn-ghost btn-sm" :disabled="busy" @click="load">Refresh</button></div>
    <section class="card scope"><div class="card-body">
      <h3>Target devices <span class="badge badge-outline">{{ selectedDeviceIds.length }} selected</span></h3>
      <div class="device-options"><label v-for="device in devices" :key="device.id" class="checkbox-label"><input v-model="selectedDeviceIds" type="checkbox" :value="device.id" :disabled="busy" /><span>{{ device.name }}<small v-if="device.recovery_required">Recovery required</small><small v-else-if="device.facts_stale">Scan before changes</small></span><router-link :to="`/devices/${device.id}`">Details</router-link></label></div>
      <p v-if="!devices.length" class="muted">No SSH account-capable devices are available.</p>
      <div class="flex gap-xs"><button class="btn btn-ghost btn-sm" @click="selectedDeviceIds = devices.map(d => d.id)">Select all {{ devices.length }} devices</button><button class="btn btn-ghost btn-sm" @click="selectedDeviceIds = []">Clear</button><button class="btn btn-primary btn-sm" :disabled="!selectedDeviceIds.length || busy" @click="inspect">Inspect accounts</button></div>
      <p class="muted">Inspections refresh groups, login shells, and sudo policy. Cached observations are marked unverified after a change.</p>
    </div></section>
    <div class="tabs"><button :class="['tab', {active: tab === 'manage'}]" @click="tab = 'manage'">Accounts and privileges</button><button :class="['tab', {active: tab === 'add'}]" @click="tab = 'add'">Provision accounts</button></div>
    <section v-if="tab === 'manage'">
      <div class="flex gap-xs toolbar"><input v-model="search" class="form-input" aria-label="Search accounts" placeholder="Search accounts" /><button class="btn btn-ghost btn-sm" :disabled="!selectedUsers.length || !selectedDeviceIds.length || busy" @click="prepare('reset', selectedUsers)">Reset {{ selectedUsers.length || 'selected' }} passwords</button><button class="btn btn-ghost btn-sm" :disabled="!selectedUsers.length || !selectedDeviceIds.length || busy" @click="prepare('edit', selectedUsers)">Edit groups / shell</button></div>
      <p v-if="!selectedDeviceIds.length" class="callout">Choose devices above to review their account state.</p>
      <div v-else class="table-wrapper"><table><thead><tr><th>Select</th><th>Account</th><th>Observed state on selected devices</th><th>Actions</th></tr></thead><tbody>
        <tr v-for="user in filteredUsers" :key="user.id">
          <td><input v-model="selectedUsers" type="checkbox" :value="user.username" :aria-label="`Select ${user.username}`" /></td>
          <td><strong>{{ user.username }}</strong><small>{{ user.full_name }}</small></td>
          <td><div v-for="device in selectedDevices" :key="device.id" class="placement"><strong>{{ device.name }}</strong><span>{{ privilegeLabel(accountPlacement(user, device.id)) }}</span><template v-if="accountPlacement(user, device.id).state === 'observed'"><small>Groups: {{ accountPlacement(user, device.id).groups || 'None' }} · {{ accountPlacement(user, device.id).shell }}</small><small>Observed {{ formatLongTime(accountPlacement(user, device.id).observed_at) }}</small><details><summary>Effective sudo policy</summary><pre>{{ accountPlacement(user, device.id).sudo_policy || 'Not reported' }}</pre></details></template></div></td>
          <td><div class="account-actions"><button v-for="action in rowActions" :key="action.id" class="btn btn-ghost btn-sm" :disabled="busy" @click="prepare(action.id, [user.username])">{{ action.label }}</button></div></td>
        </tr>
      </tbody></table><p v-if="!filteredUsers.length" class="muted empty">No recorded accounts. Inspect selected devices to discover them.</p></div>
      <p class="muted">A managed grant is the passwordless rule in /etc/sudoers.d/&lt;username&gt;. Removing it can leave privileges granted by groups or other sudo policies. Review the effective policy above.</p>
    </section>
    <section v-else class="card"><div class="card-body">
      <h3>Provision accounts</h3><p class="muted">New accounts use the system home directory defaults. Existing accounts and their configuration files are preserved. An account created without a password has password login locked.</p>
      <div v-for="(user, i) in newUsers" :key="i" class="new-user"><input v-model="user.full_name" class="form-input" :aria-label="`Full name ${i + 1}`" placeholder="Full name" /><input v-model="user.email" class="form-input" :aria-label="`Email ${i + 1}`" placeholder="name@example.com" /><button class="btn btn-ghost btn-sm" :disabled="newUsers.length === 1" @click="newUsers.splice(i, 1)">Remove</button></div>
      <button class="btn btn-ghost btn-sm" @click="newUsers.push({full_name: '', email: ''})">Add row</button><details><summary>Import CSV</summary><CsvUpload @parsed="csvUsers = $event" /><p v-if="csvUsers.length">{{ csvUsers.length }} CSV accounts replace the manual entries for this request. <button class="btn btn-ghost btn-sm" @click="csvUsers = []">Clear CSV</button></p></details>
      <button class="btn btn-primary" :disabled="!usersToAdd.length || !selectedDeviceIds.length || busy" @click="prepare('add', usersToAdd.map(u => u.email.split('@')[0]))">Review provisioning</button>
    </div></section>
    <BaseModal :visible="!!pending" :title="pending?.title || ''" @cancel="close">
      <template v-if="pending">
        <p><strong>Accounts:</strong> {{ pending.names.join(', ') }}</p><p><strong>Devices:</strong> {{ pending.devices.map(d => d.name).join(', ') }}</p><p>{{ pending.description }}</p>
        <template v-if="['password', 'reset', 'add'].includes(pending.action)"><label class="form-label" for="account-password">{{ pending.action === 'add' ? 'Initial password (optional)' : 'New password (at least 12 characters)' }}</label><input id="account-password" v-model="password" type="password" autocomplete="new-password" class="form-input" /><label v-if="pending.action === 'password'" class="checkbox-label"><input v-model="forceChange" type="checkbox" />Require password change at next login</label></template>
        <template v-if="pending.action === 'edit'"><label class="form-label" for="account-groups">Append supplementary groups (comma-separated)</label><input id="account-groups" v-model.trim="groups" class="form-input" placeholder="developers,users" /><label class="form-label" for="account-shell">Login shell</label><select id="account-shell" v-model="shell" class="form-select"><option value="">Keep current shell</option><option v-for="value in shells" :key="value">{{ value }}</option></select></template>
        <label class="form-label" for="scope-confirmation">Type CHANGE to confirm this exact scope</label><input id="scope-confirmation" v-model="typed" class="form-input" autocomplete="off" />
        <p v-if="error" class="callout callout-danger" role="alert">{{ error }}</p>
      </template>
      <template #actions><button class="btn btn-ghost" :disabled="busy" @click="close">Cancel</button><button class="btn btn-primary" :disabled="!canSubmit || busy" @click="submit">{{ busy ? 'Starting…' : 'Start operation' }}</button></template>
    </BaseModal>
  </div>
</template>
<script setup>
import {ref, computed, onMounted} from 'vue';
import {useRouter} from 'vue-router';
import {getDevices, getUsers, inspectAccounts, bulkAddUsers, bulkUpdateUsers, changePassword, bulkPasswordReset, addSudoers, removeSudoers, removeUser} from '../api.js';
import CsvUpload from '../components/CsvUpload.vue';
import BaseModal from '../components/BaseModal.vue';
import {accountPlacement, privilegeLabel} from '../utils/access.js';
import {formatLongTime} from '../utils/time.js';
const router = useRouter();
const devices = ref([]), users = ref([]), selectedDeviceIds = ref([]), selectedUsers = ref([]), search = ref(''), tab = ref('manage'), busy = ref(false);
const newUsers = ref([{full_name: '', email: ''}]), csvUsers = ref([]), pending = ref(null), password = ref(''), forceChange = ref(true), groups = ref(''), shell = ref(''), typed = ref(''), error = ref('');
const shells = ['/bin/bash', '/bin/sh', '/bin/zsh', '/usr/bin/bash', '/usr/bin/zsh', '/usr/sbin/nologin', '/bin/false'];
const rowActions = [{id:'password', label:'Password'}, {id:'grant', label:'Grant passwordless sudo'}, {id:'revoke', label:'Remove managed sudo'}, {id:'edit', label:'Groups / shell'}, {id:'remove', label:'Remove account'}];
const selectedDevices = computed(() => devices.value.filter(d => selectedDeviceIds.value.includes(d.id)));
const filteredUsers = computed(() => users.value.filter(u => `${u.username} ${u.full_name || ''} ${u.email || ''}`.toLowerCase().includes(search.value.toLowerCase())));
const usersToAdd = computed(() => csvUsers.value.length ? csvUsers.value : newUsers.value.filter(u => u.full_name && u.email));
const canSubmit = computed(() => pending.value && typed.value === 'CHANGE' && (!['password','reset'].includes(pending.value.action) || password.value.length >= 12) && (pending.value.action !== 'add' || !password.value || password.value.length >= 12) && (pending.value.action !== 'edit' || groups.value || shell.value));
async function load() { try { const [d, u] = await Promise.all([getDevices(), getUsers()]); devices.value = d.filter(d => d.transport === 'ssh' && d.capabilities.includes('users.manage')); users.value = u; selectedDeviceIds.value = selectedDeviceIds.value.filter(id => devices.value.some(d => d.id === id)); } catch(e) { window.$toast?.error("Couldn't load access state", e); } }
function prepare(action, names) { if (busy.value || !selectedDevices.value.length || !names.length) return; password.value = ''; groups.value = ''; shell.value = ''; typed.value = ''; error.value = ''; forceChange.value = true; pending.value = {action, requestKey:crypto.randomUUID(), names: [...names], devices: selectedDevices.value.map(d => ({...d})), users: usersToAdd.value.map(u => ({...u})), title: action === 'add' ? 'Provision accounts' : action === 'reset' ? 'Reset selected passwords' : rowActions.find(a => a.id === action)?.label, description: ({grant: 'Grants unrestricted passwordless root access to these accounts on each selected device.', revoke: 'Removes the named managed sudo rule. Other sudo policies and group privileges may remain.', remove: 'Removes these accounts and their managed sudo rules. Home directories are preserved.', edit: 'Adds groups without removing existing memberships. The requested login shell must exist on every target.', reset: 'Changes only the named accounts. Requires a new password at next login.', add: 'Creates missing accounts only. A supplied initial password must be changed at first login.'})[action] || 'Changes only this account on the selected devices.'}; }
function close() { if (busy.value) return; pending.value = null; password.value = ''; }
async function go(result) { window.$toast?.success(result.detail || 'Operation queued'); await router.push({path:'/activity', query:{job: result.job_id}}); }
async function inspect() { if (busy.value || !selectedDeviceIds.value.length) return; busy.value = true; try { await go(await inspectAccounts({device_ids:[...selectedDeviceIds.value]})); } catch(e) { window.$toast?.error("Couldn't inspect accounts", e); } finally { busy.value = false; } }
async function submit() {
  if (!canSubmit.value || busy.value) return;
  busy.value = true; error.value = '';
  const p = pending.value, scope = {device_ids:p.devices.map(d => d.id), request_key:p.requestKey};
  try {
    let result;
    if (p.action === 'add') result = await bulkAddUsers({...scope, users:p.users, password:password.value || null});
    else if (p.action === 'reset') result = await bulkPasswordReset({...scope, usernames:p.names, temp_password:password.value});
    else if (p.action === 'edit') result = await bulkUpdateUsers({...scope, usernames:p.names, groups:groups.value || null, shell:shell.value || null});
    else if (p.action === 'password') result = await changePassword(p.names[0], {...scope, new_password:password.value, force_change:forceChange.value});
    else if (p.action === 'grant') result = await addSudoers(p.names[0], scope);
    else if (p.action === 'revoke') result = await removeSudoers(p.names[0], scope);
    else result = await removeUser(p.names[0], {...scope, remove_home:false});
    password.value = ''; pending.value = null; await go(result);
  } catch(e) { error.value = e.message; } finally { busy.value = false; }
}
onMounted(load);
</script>
<style scoped>
.muted, small { color: var(--text-secondary); }.scope { margin-bottom: 18px; }.device-options { display: grid; grid-template-columns: repeat(auto-fit,minmax(230px,1fr)); gap: 8px; margin-bottom: 14px; }.device-options .checkbox-label { border: 1px solid var(--border-subtle); border-radius: 6px; padding: 10px; }.device-options span { flex: 1; }.device-options a, small { font-size: 12px; }small { display: block; margin-top: 4px; }.toolbar { margin: 14px 0; flex-wrap: wrap; }.toolbar input { max-width: 280px; }.account-actions { display:flex; flex-wrap:wrap; max-width:250px; gap:5px; }.placement { display:grid; gap:4px; padding:8px 0; border-bottom:1px solid var(--border-subtle); }.placement pre { white-space:pre-wrap; overflow-wrap:anywhere; max-width:600px; }.new-user { display:flex; gap:8px; margin-bottom:10px; }.empty { padding:18px; }.form-label { margin-top:16px; }details { margin:10px 0; }summary { cursor:pointer; }@media(max-width:700px){ .new-user { flex-wrap:wrap; }.device-options { grid-template-columns:1fr; } }
</style>
