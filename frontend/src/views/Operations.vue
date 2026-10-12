<template>
  <div class="maintenance">
    <header class="page-header">
      <div><h2>Operations</h2><p class="page-subtitle">Scan devices first, then run checks and maintenance with current facts.</p></div>
      <button class="btn btn-ghost btn-sm" :disabled="loading || busy" @click="load"><i :class="['fas', loading ? 'fa-spinner fa-spin' : 'fa-sync-alt']" aria-hidden="true"></i>Refresh</button>
    </header>
    <div v-if="loadError" class="callout callout-danger" role="alert">{{ loadError }} <button class="btn btn-ghost btn-sm" @click="load">Try again</button></div>
    <p v-if="loading && !devices.length" role="status" class="loading-state">Loading devices and operations…</p>
    <div v-else-if="!devices.length && !loadError" class="empty-state card"><h3>Your maintenance workspace</h3><p>Add an SSH node or Reachy Mini to run checks and maintenance.</p><router-link to="/devices?add=1" class="btn btn-primary">Add device</router-link></div>
    <div v-else class="workspace">
      <aside class="card devices-panel" aria-labelledby="device-heading">
        <div class="panel-heading"><div><h3 id="device-heading">Devices</h3><p aria-live="polite">{{ selectedIds.length }} selected</p></div><router-link to="/devices" class="subtle-link">Manage</router-link></div>
        <div class="selection-tools"><label class="visually-hidden" for="device-search">Find a device</label><input id="device-search" v-model="search" type="search" class="form-input" placeholder="Find a device…" /><div><button class="text-button" :disabled="busy" @click="selectVisible">Select visible</button><button class="text-button" :disabled="busy || !selectedIds.length" @click="selectedIds = []">Clear</button></div></div>
        <div class="device-list">
          <label v-for="device in visibleDevices" :key="device.id" :class="['device-option', {selected:selectedIds.includes(device.id)}]">
            <input v-model="selectedIds" type="checkbox" :value="device.id" :disabled="busy" />
            <span class="device-copy"><strong>{{ device.name }}</strong><small>{{ device.os_version || device.os_family || device.model || 'OS not discovered' }}</small><small v-if="needsScan(device, now)" class="warning-text">Scan required</small><small v-if="device.recovery_required" class="warning-text">{{ device.transport === 'reachy_daemon' ? 'Previous daemon operation needs verification' : 'Health checks run before install or cleanup' }}</small><small v-else-if="device.status === 'offline'" class="warning-text">Last seen offline</small></span>
          </label>
          <p v-if="!visibleDevices.length" class="muted list-empty">No devices match “{{ search }}”.</p>
        </div>
        <p v-if="missingTargets.length" class="selection-warning" role="alert">Unavailable targets: {{ missingTargets.join(', ') }}. <button class="text-button" :disabled="busy" @click="clearMissing">Remove unavailable targets</button></p>
        <p class="selection-note">Actions use exactly your selection.</p>
      </aside>

      <div class="main-panel">
        <div v-if="scanRequired.length" class="callout callout-warn" role="status"><div><strong>Scan devices before other actions</strong><p>{{ scanRequired.map(d => d.name).join(', ') }}: facts are missing or stale. A successful scan is valid for one hour.</p><button class="btn btn-primary btn-sm" :disabled="busy || loading || !!loadError || !!missingTargets.length" @click="choose(SCAN)">Scan selected devices</button></div></div>
        <div class="action-grid" aria-label="Available operations">
          <article v-for="action in visibleActions" :key="action.id" :class="['card', 'action-card', {chosen:focused === action.id}]">
            <span class="action-icon" aria-hidden="true"><i :class="['fas', action.icon]"></i></span>
            <h3>{{ action.label }}</h3><p>{{ action.description }}</p>
            <span class="action-meta">{{ action.meta }}</span>
            <button class="btn btn-primary" :disabled="!selectedIds.length || busy || loading || !!loadError || !!missingTargets.length" @click="choose(action.id)">{{ starting === action.id ? 'Starting…' : action.cta }}</button>
          </article>
        </div>
        <router-link :to="{path:'/access', query:{devices:selectedIds.join(',')}}" class="users-link">Manage users <span>Add or edit accounts in bulk, including CSV imports</span><i class="fas fa-arrow-right" aria-hidden="true"></i></router-link>
        <p v-if="!selectedIds.length" class="selection-prompt">Select devices to get started.</p>
        <div v-if="selectionBlockers.length" class="card blocked-panel" role="status">
          <h3>{{ focusedLabel }} needs attention</h3><p>Every selected device must support this action. Update your selection or resolve these issues.</p>
          <div v-for="item in selectionBlockers" :key="item.id" class="blocked-device"><div><strong>{{ item.name }}</strong><p>{{ item.reason }}</p></div><div class="blocked-actions"><router-link :to="`/devices/${item.id}`">Settings</router-link><button class="text-button" :disabled="busy" @click="selectedIds = selectedIds.filter(id => id !== item.id)">Deselect</button></div></div>
        </div>

        <section v-if="confirmation" ref="resultPanel" class="card review-panel" aria-labelledby="review-heading" tabindex="-1">
          <span class="eyebrow">Review and run</span><h3 id="review-heading">{{ confirmation.id === INSTALL ? 'Install checked apt updates?' : confirmation.id === REBOOT ? 'Reboot selected nodes?' : confirmation.id === REACHY_RESTART ? 'Restart Reachy Mini daemon?' : 'Clear unused container cache?' }}</h3>
          <p class="target-line">{{ selectedDevices.map(d => d.name).join(', ') }}</p><p v-if="[INSTALL, CLEANUP].includes(confirmation.id) && selectedDevices.some(d => d.recovery_required)" class="muted">An earlier operation did not finish. We’ll check device health first, then continue automatically. If a device needs attention, this action stops before making changes.</p>
          <template v-if="confirmation.id === INSTALL"><p>{{ packageCount(check) }} package {{ packageCount(check) === 1 ? 'update' : 'updates' }} across {{ selectedDevices.length }} {{ selectedDevices.length === 1 ? 'device' : 'devices' }}. Services may restart. No automatic reboot.</p><PackageResults :reports="check.result_artifacts" :devices="devices" /></template>
          <template v-else-if="confirmation.id === REBOOT"><p>Reboot every selected node, including nodes with pending health checks. Running work will be interrupted.</p><p class="muted">Nodes restart one at a time. We’ll wait for each node to return over SSH and refresh its details.</p></template>
          <template v-else-if="confirmation.id === REACHY_RESTART"><p>Restart the daemon on the selected Reachy Mini devices. Connected apps are interrupted, and the robot may move during initialization.</p><p class="muted">Devices are handled one at a time. We’ll wait for the daemon to finish restarting and verify the robot backend is ready.</p></template>
          <template v-else><p>Remove unused images and build cache from Docker and containerd/nerdctl. Containers, volumes, and networks stay intact.</p><p class="muted">Removed images may need to be downloaded again. BuildKit cache is cleared when available.</p></template>
          <div class="review-actions"><button class="btn btn-primary" :disabled="busy || loading || !!loadError || !!selectionBlockers.length || (confirmation.id === INSTALL && !checkReady)" @click="confirmRun">{{ confirmation.id === INSTALL ? `Install ${updateLabel(packageCount(check))}` : confirmation.id === REBOOT ? 'Reboot now' : confirmation.id === REACHY_RESTART ? 'Restart daemon' : 'Clear cache' }}</button><button class="btn btn-ghost" @click="confirmation = null">Cancel</button></div>
          <p v-if="confirmation.id === INSTALL && !checkReady" role="alert" class="warning-text">This check expired or the selection changed. Check for updates again.</p>
        </section>

        <div v-if="actionError" class="callout callout-danger action-error" role="alert"><div><strong>{{ actionError }}</strong><p v-if="retryRequest">The request may have been accepted. Retry safely to reconnect to the same job.</p><button v-if="retryRequest" class="btn btn-ghost btn-sm" :disabled="starting !== ''" @click="submit(retryRequest)">Reconnect to request</button></div></div>

        <section v-if="job && !(confirmation?.id === INSTALL && job.playbook === 'package_preview.yml')" ref="jobPanel" class="card result-panel" aria-labelledby="result-heading" tabindex="-1">
          <div class="result-heading"><div><span class="eyebrow">{{ job.playbook === 'host_facts.yml' ? 'Device discovery' : job.playbook === 'package_preview.yml' ? 'Package check' : job.playbook === 'docker_cleanup.yml' ? 'Cache cleanup' : job.playbook === 'system_update.yml' ? 'Package installation' : job.playbook === 'reboot.yml' ? 'Node reboot' : job.playbook === 'storage_analysis.yml' ? 'Storage check' : job.playbook === 'gpu_usage.yml' ? 'GPU check' : job.playbook === REACHY_RESTART ? 'Reachy Mini daemon restart' : 'Device verification' }}</span><h3 id="result-heading">{{ jobHeadline }}</h3></div><span role="status" :class="['result-state', {failed:job.status !== 'success' && !jobActive}]"><i v-if="jobActive" class="fas fa-spinner fa-spin" aria-hidden="true"></i>{{ statusLabel(job.status) }}</span></div>
          <p class="muted">{{ job.playbook === 'storage_analysis.yml' ? `${namesFor(job).length} ${namesFor(job).length === 1 ? 'node' : 'nodes'}` : namesFor(job).map(name => devices.find(d => d.inventory_name === name)?.name || name).join(', ') }} <span v-if="job.finished_at">· {{ formatLongTime(job.finished_at) }}</span></p>
          <p v-if="jobActive" role="status">{{ jobProgress }}</p>
          <div v-if="pollError" class="callout callout-warn" role="alert">{{ pollError }} <button class="btn btn-ghost btn-sm" @click="pollJob(job.job_id)">Reconnect</button></div>
          <p v-if="job.error_summary" class="warning-text">{{ job.error_summary }}</p>
          <div v-for="outcome in visibleStorageOutcomes(job)" :key="outcome.hostname" class="outcome"><strong>{{ devices.find(d => d.inventory_name === outcome.hostname)?.name || outcome.hostname }}</strong><span>{{ statusLabel(outcome.status) }}</span><p v-if="outcome.detail">{{ outcome.detail }}</p><p v-if="outcome.recovery_resolution">{{ outcome.recovery_resolution }}</p></div>
          <PackageResults v-if="job.playbook === 'package_preview.yml'" :reports="job.result_artifacts || []" :devices="devices" />
          <div v-for="report in (job.result_artifacts || []).filter(r => r.report_type === 'apt_install')" :key="report.hostname" class="install-summary"><strong>{{ report.hostname }}</strong>: {{ report.package_count }} {{ report.package_count === 1 ? 'package' : 'packages' }} installed.<span v-if="report.reboot_required" class="warning-text"> Reboot required. Use Reboot nodes when ready.</span></div>
          <div v-for="report in (job.result_artifacts || []).filter(r => r.report_type === 'cleanup')" :key="report.hostname" class="cleanup-summary"><h4>{{ report.hostname }}</h4><p>{{ report.summary }}</p><details v-for="step in report.steps" :key="step.label"><summary>{{ step.label }} · {{ step.status === 'skipped' ? 'Skipped' : statusLabel(step.status) }}</summary><pre>{{ step.output || 'Nothing to remove.' }}</pre></details></div>
          <DiscoveryResults :reports="job.result_artifacts || []" :devices="devices" />
          <InspectionResults :reports="job.result_artifacts || []" :devices="devices" />
          <div v-if="!jobActive" class="result-actions"><button v-if="checkReady && packageCount(check) > 0 && job.playbook === 'package_preview.yml'" class="btn btn-primary" :disabled="busy" @click="choose(INSTALL)">Install {{ updateLabel(packageCount(check)) }}</button><button v-if="job.status !== 'success' && job.playbook === 'package_preview.yml'" class="btn btn-ghost" :disabled="busy" @click="choose(CHECK)">Check selected devices again</button><router-link :to="{path:'/activity',query:{job:job.job_id}}">View full activity</router-link></div>
          <details v-if="job.output_log" class="output-log"><summary>Technical log</summary><pre>{{ job.output_log }}</pre></details>
        </section>
        <div v-else-if="!confirmation && !selectionBlockers.length" class="results-empty"><i class="fas fa-list-check" aria-hidden="true"></i><h3>Results stay right here</h3><p>Run a check or maintenance action and follow each device without leaving this page.</p></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import PackageResults from '../components/PackageResults.vue';
import InspectionResults from '../components/InspectionResults.vue';
import DiscoveryResults from '../components/DiscoveryResults.vue';
import {visibleStorageOutcomes} from '../utils/storage.js';
import { getDevices, getOperations, runOperation, getJobs, getJob } from '../api.js';
import { parseDeviceIds } from '../utils/fleetOverview.js';
import { formatLongTime } from '../utils/time.js';
import { SCAN, needsScan, CHECK, INSTALL, CLEANUP, REBOOT, STORAGE, GPU, REACHY_RESTART, PLAYBOOKS, ACTION_IDS, ACTIVE, namesFor, sameTargets, validPackageCheck, blockers, packageCount, statusLabel, updateLabel } from '../utils/maintenance.js';


const actions = [
  {id:SCAN,label:'Scan devices',description:'Discover hardware, software, health, and supported capabilities for every selected device.',meta:'Required first · Facts valid for one hour',cta:'Scan now',icon:'fa-magnifying-glass'},
  {id:CHECK,label:'Check for apt updates',description:'See which packages can be updated on your Debian and Ubuntu devices.',meta:'No packages installed',cta:'Check now',icon:'fa-magnifying-glass'},
  {id:INSTALL,label:'Install apt updates',description:'Review available updates, then install the checked versions.',meta:'One device at a time · No reboot',cta:'Review & install',icon:'fa-arrow-down'},
  {id:CLEANUP,label:'Clear container cache',description:'Clear unused Docker and containerd/nerdctl images and build cache.',meta:'Keep containers and volumes',cta:'Clear cache…',icon:'fa-box'},
  {id:STORAGE,label:'Check storage',description:'See capacity for the filesystem containing /home and every mount in /etc/fstab.',meta:'Read only · Flags missing mounts',cta:'Check storage',icon:'fa-hard-drive'},
  {id:GPU,label:'Check GPU usage',description:'See GPU utilization, memory, process owners, and container or pod context.',meta:'Read only · NVIDIA GPU nodes',cta:'Check GPUs',icon:'fa-microchip'},
  {id:REACHY_RESTART,label:'Restart Reachy Mini daemon',description:'Restart the daemon and verify the robot backend is ready.',meta:'Reachy Mini only · Interrupts connected apps',cta:'Restart daemon…',icon:'fa-robot'},
  {id:REBOOT,label:'Reboot nodes',description:'Restart selected nodes, even when no reboot is marked as required.',meta:'One node at a time · Interrupts running work',cta:'Reboot…',icon:'fa-power-off'},
];
const route = useRoute(), router = useRouter();
const devices = ref([]), operations = ref([]), selectedIds = ref(parseDeviceIds(route.query.devices || route.query.device));
const loading = ref(true), loadError = ref(''), search = ref(''), starting = ref(''), focused = ref(ACTION_IDS.includes(route.query.operation) ? route.query.operation : ''), confirmation = ref(null), actionError = ref(''), retryRequest = ref(null);
const job = ref(null), check = ref(null), pollError = ref(''), now = ref(Date.now()), resultPanel = ref(null), jobPanel = ref(null), unresolvedNames = ref([]);
let installAfterCheck = false;
let timer, clockTimer, disposed = false, generation = 0, selectionGeneration = 0, initialized = false;
const selectedDevices = computed(() => devices.value.filter(d => selectedIds.value.includes(d.id)));
const scanRequired = computed(() => selectedDevices.value.filter(d => needsScan(d, now.value)));
const visibleActions = computed(() => actions.filter(action => action.id !== REACHY_RESTART || selectedDevices.value.some(device => device.transport === 'reachy_daemon' && device.kind === 'robot' && /^reachy[\s_-]+mini(?:[\s_-]|$)/i.test(device.model || ''))));
const visibleDevices = computed(() => devices.value.filter(d => `${d.name} ${d.inventory_name} ${d.os_version}`.toLowerCase().includes(search.value.toLowerCase())));
const missingTargets = computed(() => [...unresolvedNames.value, ...selectedIds.value.filter(id => !devices.value.some(d => d.id === id)).map(id => `#${id}`)]);
const jobActive = computed(() => job.value && ACTIVE.includes(job.value.status));
const busy = computed(() => !!starting.value || !!jobActive.value || !!retryRequest.value);
const checkReady = computed(() => !missingTargets.value.length && validPackageCheck(check.value, selectedDevices.value, now.value));
const focusedLabel = computed(() => actions.find(a => a.id === focused.value)?.label || 'This action');
const selectionBlockers = computed(() => {
  if (!focused.value) return [];
  const unavailable = blockers(operations.value.find(o => o.id === focused.value), selectedIds.value, devices.value);
  if (focused.value !== SCAN) for (const device of scanRequired.value) {
    if (!unavailable.some(item => item.id === device.id)) unavailable.push({id:device.id,name:device.name,reason:'Scan devices first. Device facts are missing or stale.'});
  }
  return unavailable;
});
const jobHeadline = computed(() => {
  if (jobActive.value && job.value.playbook === 'host_facts.yml') return job.value.status === 'pending' ? 'Scan queued' : 'Scanning devices';
  if (jobActive.value) return job.value.status === 'pending' ? 'Waiting to start…' : ['checking_health','checking_facts'].includes(job.value.phase) ? 'Checking device health' : 'Operation in progress';
  if (job.value.phase === 'health_check_failed') return 'Device health check failed';
  if (job.value.status !== 'success') return job.value.status === 'partial' ? 'Some devices need attention' : 'This operation needs attention';
  if (job.value.playbook === 'package_preview.yml') return packageCount(job.value) ? `${packageCount(job.value)} package ${packageCount(job.value) === 1 ? "update" : "updates"} available` : 'All packages are up to date';
  return job.value.playbook === 'host_facts.yml' ? 'Device scan completed' : job.value.playbook === 'system_update.yml' ? 'Apt updates installed' : job.value.playbook === 'docker_cleanup.yml' ? 'Cache cleanup completed' : job.value.playbook === 'reboot.yml' ? 'Nodes rebooted' : job.value.playbook === 'storage_analysis.yml' ? 'Storage check completed' : job.value.playbook === 'gpu_usage.yml' ? 'GPU check completed' : job.value.playbook === REACHY_RESTART ? 'Reachy Mini daemon restarted' : 'Device details verified';
});
function selectVisible() { selectedIds.value = [...new Set([...selectedIds.value, ...visibleDevices.value.map(d => d.id)])]; }
function clearMissing() { selectedIds.value = selectedIds.value.filter(id => devices.value.some(d => d.id === id)); unresolvedNames.value = []; }
const jobProgress = computed(() => ({scanning:'Discovering device hardware, software, health, and supported capabilities. Failed devices remain blocked until a scan succeeds.',checking_health:'Checking services, storage mounts, package health, and detected GPUs after an unfinished operation. Your action will continue automatically.', checking_facts:'Refreshing device details before continuing automatically.', refreshing_facts:'The action finished. Refreshing device details…'})[job.value?.phase] || (job.value?.playbook === 'reboot.yml' ? 'Rebooting selected nodes one at a time and waiting for SSH to return. You can leave this page and follow progress in Activity.' : job.value?.playbook === REACHY_RESTART ? 'Restarting Reachy Mini daemons one at a time and waiting for the robot backend to be ready. You can follow progress in Activity.' : 'Working on the selected devices. You can leave this page and return to Activity at any time.'));
async function focusPanel(panel) { await nextTick(); panel.value?.focus({preventScroll:true}); panel.value?.scrollIntoView({behavior:'smooth',block:'nearest'}); }
async function load() {
  loading.value = true; loadError.value = '';
  try {
    const [allDevices, allOperations] = await Promise.all([getDevices(), getOperations()]);
    if (disposed) return;
    devices.value = allDevices; operations.value = allOperations;
    if (!initialized) {
      initialized = true;
      if (route.query.targets) {
        const names = namesFor({target_devices:route.query.targets});
        selectedIds.value = devices.value.filter(d => names.includes(d.inventory_name)).map(d => d.id);
        unresolvedNames.value = names.filter(name => !devices.value.some(d => d.inventory_name === name));
      }
      if (route.query.preview || route.query.job) {
        const restored = await getJob(route.query.job || route.query.preview);
        job.value = restored;
        if (route.query.preview && !selectedIds.value.length) selectedIds.value = devices.value.filter(d => namesFor(restored).includes(d.inventory_name)).map(d => d.id);
        if (restored.playbook === 'package_preview.yml') check.value = restored;
        if (ACTIVE.includes(restored.status)) await pollJob(restored.job_id);
      }
    }
    await restoreCheck();
  } catch (error) { loadError.value = `Could not refresh operations. ${error.message}`; }
  finally { loading.value = false; }
}
async function restoreCheck() {
  const version = ++selectionGeneration;
  if (!selectedDevices.value.length || missingTargets.value.length || checkReady.value || jobActive.value) return;
  try {
    const recent = await getJobs({playbook:'package_preview.yml',status:'success',limit:50});
    if (disposed || version !== selectionGeneration) return;
    const matching = recent.find(j => sameTargets(j, selectedDevices.value));
    const result = matching ? await getJob(matching.job_id) : null;
    if (!disposed && version === selectionGeneration) check.value = result;
  } catch { /* A fresh check is always available when history cannot be loaded. */ }
}
watch(selectedIds, () => { confirmation.value = null; actionError.value = ''; installAfterCheck = false; void restoreCheck(); }, {deep:true});
async function choose(id) {
  if (busy.value || loading.value || loadError.value || !selectedIds.value.length || missingTargets.value.length) return;
  focused.value = id; actionError.value = ''; confirmation.value = null; installAfterCheck = id === INSTALL;
  if (selectionBlockers.value.length) return;
  if ([SCAN, STORAGE, GPU].includes(id)) {
    await submit(makeRequest(id));
  } else if (id === CHECK || (id === INSTALL && !checkReady.value)) {
    // The installation entry point runs a check first, then opens its package
    // review in place. No background auto-install follows a check.
    await submit(makeRequest(CHECK));
  } else if (id === INSTALL && packageCount(check.value) === 0) {
    job.value = check.value;
  } else {
    confirmation.value = {id};
    await focusPanel(resultPanel);
  }
}
function makeRequest(id) {
  const ordered = [...selectedDevices.value].sort((a,b) => a.inventory_name < b.inventory_name ? -1 : a.inventory_name > b.inventory_name ? 1 : 0);
  return {id, ids:[...selectedIds.value], parameters:{request_key:crypto.randomUUID(), confirmation:ordered.map(d => d.name).join(', '), ...(id === INSTALL ? {preview_job_id:check.value.job_id} : {})}};
}
async function confirmRun() {
  if (!confirmation.value || busy.value || loading.value || loadError.value || selectionBlockers.value.length || (confirmation.value.id === INSTALL && !checkReady.value)) return;
  const request = makeRequest(confirmation.value.id); confirmation.value = null;
  await submit(request);
}
async function submit(request) {
  starting.value = request.id; actionError.value = ''; retryRequest.value = null;
  try {
    const result = await runOperation(request.id, request.ids, request.parameters);
    job.value = {job_id:result.job_id,status:'pending',playbook:PLAYBOOKS[request.id],target_devices:devices.value.filter(d => request.ids.includes(d.id)).map(d => d.inventory_name).join(',')};
    if (request.id === INSTALL) check.value = null;
    await router.replace({query:{devices:request.ids.join(','),job:result.job_id}});
    await pollJob(result.job_id);
    await focusPanel(confirmation.value ? resultPanel : jobPanel);
  } catch (error) {
    actionError.value = error.message;
    if (!error.status || error.status >= 500) retryRequest.value = request;
    else await load();
  } finally { starting.value = ''; }
}
async function pollJob(id) {
  clearTimeout(timer); const current = ++generation;
  try {
    const result = await getJob(id);
    if (disposed || current !== generation) return;
    now.value = Date.now(); job.value = result; pollError.value = '';
    if (ACTIVE.includes(result.status)) timer = setTimeout(() => pollJob(id), 2000);
    else {
      if (result.playbook === 'package_preview.yml') check.value = result;
      try { [devices.value, operations.value] = await Promise.all([getDevices(), getOperations()]); loadError.value = ''; }
      catch { loadError.value = 'Could not refresh device readiness. Refresh before starting another action.'; }
      if (installAfterCheck && result.playbook === 'package_preview.yml') {
        installAfterCheck = false;
        if (checkReady.value && packageCount(check.value) > 0 && !selectionBlockers.value.length) {
          confirmation.value = {id:INSTALL};
          await focusPanel(resultPanel);
        }
      }
    }
  } catch (error) {
    if (disposed || current !== generation) return;
    pollError.value = `Live updates disconnected. The operation may still be running. ${error.message}`;
    timer = setTimeout(() => pollJob(id), 5000);
  }
}
onMounted(() => { void load(); clockTimer = setInterval(() => { now.value = Date.now(); }, 1000); });
onUnmounted(() => { disposed = true; generation++; selectionGeneration++; clearTimeout(timer); clearInterval(clockTimer); });
</script>

<style scoped>
.main-panel > .callout { margin-bottom:16px; }
.users-link { display:flex; align-items:center; gap:12px; padding:16px; margin-top:14px; border:1px solid var(--border-subtle); border-radius:6px; font-weight:600; }.users-link span { flex:1; color:var(--text-secondary); font-size:13px; font-weight:400; }@media(max-width:600px){.users-link{flex-wrap:wrap}.users-link span{flex-basis:100%}}
.page-subtitle { margin:6px 0 0; color:var(--text-secondary); }
.workspace { display:grid; grid-template-columns:290px minmax(0,1fr); gap:24px; align-items:start; }
.devices-panel { position:sticky; top:86px; overflow:hidden; }
.panel-heading { display:flex; align-items:center; justify-content:space-between; padding:20px; }
h3 { font-size:16px; margin:0; }.panel-heading p { margin:4px 0 0; color:var(--text-secondary); font-size:13px; }
.subtle-link, .text-button { color:var(--link-text); font-size:13px; }.text-button { border:0; padding:4px 0; background:none; cursor:pointer; font:inherit; font-size:13px; }.text-button:disabled { opacity:.45; cursor:default; }
.selection-tools { padding:0 20px 12px; }.selection-tools > div { display:flex; justify-content:space-between; padding-top:8px; }
.device-list { max-height:52vh; overflow:auto; }.device-option { display:flex; align-items:flex-start; gap:12px; padding:15px 20px; border-top:1px solid var(--border-subtle); cursor:pointer; }.device-option.selected { background:var(--surface-info-soft); }.device-option input { margin-top:3px; width:17px; height:17px; accent-color:var(--color-accent); flex-shrink:0; }.device-copy { min-width:0; display:grid; gap:4px; }.device-copy strong { font-size:14px; overflow-wrap:anywhere; }.device-copy small { color:var(--text-secondary); font-size:12px; line-height:1.4; }.device-copy .warning-text { color:var(--status-warning-text); }
.selection-note, .selection-warning { padding:14px 20px; margin:0; font-size:12px; color:var(--text-secondary); border-top:1px solid var(--border-subtle); }.selection-warning { color:var(--status-danger-text); }.list-empty { padding:16px; }
.main-panel { min-width:0; }.action-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }.action-card { padding:20px; display:flex; flex-direction:column; align-items:flex-start; box-shadow:none; }.action-card.chosen { border-color:var(--focus-ring); }.action-icon { display:grid; place-items:center; width:36px; height:36px; border-radius:8px; color:var(--link-text); background:var(--surface-info-soft); margin-bottom:18px; }.action-card h3 { line-height:1.4; }.action-card p { font-size:13px; color:var(--text-secondary); line-height:1.6; margin:9px 0 16px; }.action-meta { font-size:11px; color:var(--text-secondary); margin-top:auto; margin-bottom:15px; line-height:1.5; }.action-card .btn { width:100%; min-height:40px; justify-content:center; }.selection-prompt { color:var(--text-secondary); font-size:13px; margin:14px 0; }
.results-empty { text-align:center; padding:60px 24px; color:var(--text-secondary); }.results-empty i { font-size:24px; margin-bottom:16px; }.results-empty p { font-size:13px; line-height:1.6; max-width:400px; margin:8px auto; }.results-empty h3 { color:var(--text-primary); }
.review-panel, .result-panel, .blocked-panel { margin-top:22px; padding:24px; box-shadow:none; }.review-panel { border-color:var(--focus-ring); }.review-panel h3, .result-panel h3 { margin:6px 0 12px; font-size:21px; }.review-panel p, .result-panel p, .blocked-panel p { font-size:13px; line-height:1.6; }.eyebrow { font-size:10px; text-transform:uppercase; letter-spacing:1px; color:var(--text-secondary); }.target-line { font-weight:600; overflow-wrap:anywhere; }.warning-text { color:var(--status-warning-text); }.muted { color:var(--text-secondary); }.review-actions, .result-actions { display:flex; flex-wrap:wrap; align-items:center; gap:14px; margin-top:20px; }.result-actions a { font-size:13px; }.result-heading { display:flex; justify-content:space-between; gap:16px; align-items:center; }.result-state { padding:6px 10px; border-radius:20px; background:var(--surface-success-soft); font-size:12px; white-space:nowrap; }.result-state.failed { background:var(--surface-warning-soft); }.result-state i { margin-right:6px; }
.outcome { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:8px; padding:12px 0; border-bottom:1px solid var(--border-subtle); font-size:13px; }.outcome p { width:100%; margin:0; color:var(--status-warning-text); overflow-wrap:anywhere; }.install-summary { font-size:13px; padding:12px 0; }.cleanup-summary { margin-top:16px; }.cleanup-summary details { padding:8px 0; }
summary { cursor:pointer; line-height:1.5; }.output-log { border-top:1px solid var(--border-subtle); margin-top:24px; padding-top:16px; font-size:13px; }pre { margin-top:12px; white-space:pre-wrap; overflow-wrap:anywhere; max-height:360px; overflow:auto; padding:14px; background:var(--surface-light); font-size:11px; }
.blocked-device { display:flex; gap:12px; justify-content:space-between; align-items:center; padding:12px 0; border-top:1px solid var(--border-subtle); font-size:13px; }.blocked-device p { margin:4px 0 0; color:var(--text-secondary); }.blocked-actions { display:flex; gap:12px; align-items:center; flex-shrink:0; }.action-error { margin-top:20px; }.loading-state { padding:60px 0; text-align:center; color:var(--text-secondary); }
@media(max-width:1150px) { .workspace { grid-template-columns:250px minmax(0,1fr); gap:16px; }.action-grid { grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }.action-card { padding:16px; }.action-card h3 { font-size:14px; }.blocked-device { align-items:flex-start; flex-direction:column; } }
@media(max-width:900px) { .workspace { grid-template-columns:1fr; }.devices-panel { position:static; }.device-list { max-height:240px; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); }.panel-heading { padding-bottom:12px; }.selection-tools { display:flex; gap:20px; align-items:center; }.selection-tools input { flex:1; min-width:0; }.selection-tools > div { gap:16px; padding:0; }.action-card { padding:20px; } }
@media(max-width:580px) { .action-grid { grid-template-columns:1fr; }.action-card { display:grid; grid-template-columns:36px 1fr; gap:0 12px; }.action-icon { grid-row:1/4; margin:0; }.action-card p { margin:6px 0 10px; }.action-card .btn { grid-column:2; }.action-meta { grid-column:2; }.device-list { grid-template-columns:1fr; }.selection-tools { display:block; }.selection-tools > div { padding-top:8px; }.review-panel,.result-panel,.blocked-panel { padding:18px; }.result-heading { align-items:flex-start; flex-direction:column; gap:0; }.results-empty { padding:32px 12px; } }
</style>
