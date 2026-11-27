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
            <span class="device-copy"><strong>{{ device.name }}</strong><small v-if="device.inventory_name !== device.name">{{ device.inventory_name }}</small><small>{{ device.os_version || device.os_family || device.model || 'OS not discovered' }}</small><small v-if="needsScan(device, now)" class="warning-text">Scan required</small><small v-if="device.recovery_required" class="warning-text">{{ device.transport === 'reachy_daemon' ? 'Previous daemon operation needs verification' : 'Health checks run before install or cleanup' }}</small><small v-else-if="device.status === 'offline'" class="warning-text">Last seen offline</small></span>
          </label>
          <p v-if="!visibleDevices.length" class="muted list-empty">No devices match “{{ search }}”.</p>
        </div>
        <p v-if="missingTargets.length" class="selection-warning" role="alert">Unavailable targets: {{ missingTargets.join(', ') }}. <button class="text-button" :disabled="busy" @click="clearMissing">Remove unavailable targets</button></p>
        <p v-if="hiddenSelectionCount" class="selection-note" role="status">{{ hiddenSelectionCount }} selected {{ hiddenSelectionCount === 1 ? 'device' : 'devices' }} hidden by this filter. <button class="text-button" @click="search = ''">Show all devices</button></p>
      </aside>

      <div class="main-panel">
        <div v-if="scanRequired.length" class="callout callout-warn" role="status"><div><strong>Scan devices before maintenance</strong><p>{{ scanRequired.map(d => d.name).join(', ') }}: facts are missing or stale. A successful scan is valid for one hour. Find current IP remains available for SSH devices.</p><button class="btn btn-primary btn-sm" :disabled="busy || loading || !!loadError || !!missingTargets.length" @click="choose(SCAN)">Scan selected devices</button></div></div>
        <div v-if="selectionBlockers.length" ref="blockedPanel" class="card blocked-panel" role="status" tabindex="-1">
          <h3>{{ focusedLabel }} needs attention</h3><p>Every selected device must support this action. Update your selection or resolve these issues.</p>
          <div v-for="item in selectionBlockers" :key="item.id" class="blocked-device"><div><strong>{{ item.name }}</strong><p>{{ item.reason }}</p></div><div class="blocked-actions"><router-link :to="`/devices/${item.id}`">Settings</router-link><button class="text-button" :disabled="busy" @click="selectedIds = selectedIds.filter(id => id !== item.id)">Deselect</button></div></div>
        </div>

        <section v-if="confirmation" ref="resultPanel" class="card review-panel" aria-labelledby="review-heading" tabindex="-1">
          <span class="eyebrow">Review and run</span><h3 id="review-heading">{{ confirmation.id === INSTALL ? 'Install checked apt updates?' : confirmation.id === REBOOT ? 'Reboot selected nodes?' : confirmation.id === REACHY_RESTART ? 'Restart Reachy Mini daemon?' : 'Clear unused container cache?' }}</h3>
          <div class="review-targets"><strong>{{ selectedDevices.length }} {{ selectedDevices.length === 1 ? 'target' : 'targets' }}</strong>
            <ul><li v-for="device in selectedDevices" :key="device.id">{{ device.name }} <code v-if="device.inventory_name !== device.name">{{ device.inventory_name }}</code></li></ul>
          </div>
          <p v-if="[INSTALL, CLEANUP].includes(confirmation.id) && selectedDevices.some(d => d.recovery_required)" class="muted">An earlier operation did not finish. We’ll check device health first, then continue automatically. If a device needs attention, this action stops before making changes.</p>
          <template v-if="confirmation.id === INSTALL"><p>{{ packageCount(check) }} package {{ packageCount(check) === 1 ? 'update' : 'updates' }} across {{ selectedDevices.length }} {{ selectedDevices.length === 1 ? 'device' : 'devices' }}. Services may restart. No automatic reboot.</p><PackageResults :reports="check.result_artifacts" :devices="devices" /></template>
          <template v-else-if="confirmation.id === REBOOT"><p>Reboot every selected node, including nodes with pending health checks. Running work will be interrupted.</p><p class="muted">We’ll wait for each node to return over SSH and refresh its details.</p></template>
          <template v-else-if="confirmation.id === REACHY_RESTART"><p>Restart the daemon on the selected Reachy Mini devices. Connected apps are interrupted, and the robot may move during initialization.</p><p class="muted">Devices are handled one at a time. We’ll wait for the daemon to finish restarting and verify the robot backend is ready.</p></template>
          <template v-else><p>Remove unused images and build cache from Docker and containerd/nerdctl. Containers, volumes, and networks stay intact.</p><p class="muted">Removed images may need to be downloaded again. BuildKit cache is cleared when available.</p></template>
          <fieldset v-if="canChooseRollout" class="rollout-options">
            <legend>Execution order</legend>
            <div class="rollout-fields">
              <label><span>Run devices</span>
                <select id="rollout-mode" v-model="rolloutMode" class="form-select">
                  <option value="parallel">In parallel</option><option value="rolling">In rolling batches</option>
                </select>
              </label>
              <label v-if="rolloutMode === 'rolling'"><span>Devices per batch</span>
                <input id="batch-size" v-model.number="batchSize" type="number" class="form-input" min="1" :max="selectedDevices.length" step="1" :aria-invalid="!batchSizeValid" aria-describedby="batch-summary" />
              </label>
            </div>
            <p id="batch-summary" aria-live="polite" :class="batchSizeValid ? 'muted' : 'warning-text'">{{ rolloutSummary }}</p>
          </fieldset>
          <div class="review-actions"><button class="btn btn-primary" :disabled="busy || loading || !!loadError || !!selectionBlockers.length || !batchSizeValid || (confirmation.id === INSTALL && !checkReady)" @click="confirmRun">{{ confirmation.id === INSTALL ? `Install ${updateLabel(packageCount(check))}` : confirmation.id === REBOOT ? 'Reboot now' : confirmation.id === REACHY_RESTART ? 'Restart daemon' : 'Clear cache' }}</button><button class="btn btn-ghost" @click="confirmation = null">Cancel</button></div>
          <p v-if="confirmation.id === INSTALL && !checkReady" role="alert" class="warning-text">This check expired or the selection changed. Check for updates again.</p>
        </section>

        <div v-if="actionError" ref="actionErrorPanel" tabindex="-1" class="callout callout-danger action-error" role="alert"><div><strong>{{ actionError }}</strong><p v-if="retryRequest">The request may have been accepted. Retry safely to reconnect to the same job.</p><button v-if="retryRequest" class="btn btn-ghost btn-sm" :disabled="starting !== ''" @click="submit(retryRequest)">Reconnect to request</button></div></div>
        <div class="catalog-tools">
          <h3 id="catalog-heading">Operation catalog</h3>
          <label class="catalog-search"><span class="visually-hidden">Find an operation or playbook</span><input id="operation-search" v-model="operationSearch" class="form-input" type="search" placeholder="Find an operation or playbook…" /></label>
        </div>
        <p v-if="!selectedIds.length" class="selection-prompt">Select devices to run an operation.</p>
        <div class="action-grid" aria-labelledby="catalog-heading">
          <article v-for="action in visibleActions" :key="action.id" :aria-labelledby="`title-${action.id}`" :class="['card', 'action-card', {chosen:focused === action.id}]">
            <h4 :id="`title-${action.id}`">{{ action.label }}</h4>
            <small class="playbook-name">{{ executionSource(action.id) }}</small>
            <p>{{ action.description }}</p>
            <span class="action-meta">{{ action.meta }}</span>
            <span v-if="action.blocked.length" class="action-blockers">{{ action.blocked.length }} of {{ selectedIds.length }} selected unavailable</span>
            <details v-if="action.id === IP_CHECK" class="subnet-options">
              <summary>{{ discoverySubnet || 'Search a subnet' }}</summary>
              <label for="discovery-subnet">Optional IPv4 subnet</label>
              <input id="discovery-subnet" v-model.trim="discoverySubnet" class="form-input" maxlength="32" :disabled="busy" placeholder="192.0.2.0/24" aria-describedby="subnet-hint" />
              <small id="subnet-hint">Use /24 or smaller. Leave blank to check the saved endpoint and DNS.</small>
            </details>
            <button :class="['btn', action.blocked.length ? 'btn-ghost' : 'btn-primary']" :disabled="!selectedIds.length || busy || loading || !!loadError || !!missingTargets.length" @click="choose(action.id)">{{ starting === action.id ? 'Starting…' : action.blocked.length ? 'View requirements' : action.cta }}</button>
          </article>
        </div>
        <p v-if="!visibleActions.length && operationSearch.trim()" class="no-matches" role="status">No operations match “{{ operationSearch }}”. <button class="text-button" @click="operationSearch = ''">Clear search</button></p>

        <section v-if="job && !(confirmation?.id === INSTALL && job.playbook === 'package_preview.yml')" ref="jobPanel" class="card result-panel" aria-labelledby="result-heading" tabindex="-1">
          <div class="result-heading"><div><span class="eyebrow">{{ jobAction?.label || 'Operation' }}</span><h3 id="result-heading">{{ jobHeadline }}</h3></div><span role="status" :class="['result-state', {failed:job.status !== 'success' && !jobActive}]"><i v-if="jobActive" class="fas fa-spinner fa-spin" aria-hidden="true"></i>{{ statusLabel(job.status) }}</span></div>
          <p class="muted">{{ job.playbook === 'storage_analysis.yml' ? `${namesFor(job).length} ${namesFor(job).length === 1 ? 'node' : 'nodes'}` : namesFor(job).map(name => devices.find(d => d.inventory_name === name)?.name || name).join(', ') }} <span v-if="job.finished_at">· {{ formatLongTime(job.finished_at) }}</span></p>
          <p v-if="jobActive" role="status">{{ jobProgress }}</p>
          <div v-if="pollError" class="callout callout-warn" role="alert">{{ pollError }} <button class="btn btn-ghost btn-sm" @click="pollJob(job.job_id)">Reconnect</button></div>
          <p v-if="job.error_summary" class="warning-text">{{ job.error_summary }}</p>
          <div v-for="outcome in visibleStorageOutcomes(job)" :key="outcome.hostname" class="outcome"><strong>{{ devices.find(d => d.inventory_name === outcome.hostname)?.name || outcome.hostname }}</strong><span>{{ statusLabel(outcome.status) }}</span><p v-if="outcome.detail">{{ outcome.detail }}</p><p v-if="outcome.recovery_resolution">{{ outcome.recovery_resolution }}</p></div>
          <PackageResults v-if="job.playbook === 'package_preview.yml'" :reports="job.result_artifacts || []" :devices="devices" />
          <div v-for="report in (job.result_artifacts || []).filter(r => r.report_type === 'apt_install')" :key="report.hostname" class="install-summary"><strong>{{ report.hostname }}</strong>: {{ report.package_count }} {{ report.package_count === 1 ? 'package' : 'packages' }} installed.<span v-if="report.reboot_required" class="warning-text"> Reboot required. Use Reboot nodes when ready.</span></div>
          <div v-for="report in (job.result_artifacts || []).filter(r => r.report_type === 'cleanup')" :key="report.hostname" class="cleanup-summary"><h4>{{ report.hostname }}</h4><p>{{ report.summary }}</p><details v-for="step in report.steps" :key="step.label"><summary>{{ step.label }} · {{ step.status === 'skipped' ? 'Skipped' : statusLabel(step.status) }}</summary><pre>{{ step.output || 'Nothing to remove.' }}</pre></details></div>
          <DiscoveryResults :reports="job.result_artifacts || []" :devices="devices" />
          <HostIpResults :reports="job.result_artifacts || []" />
          <InspectionResults :reports="job.result_artifacts || []" :devices="devices" />
          <div v-if="!jobActive" class="result-actions"><button v-if="checkReady && packageCount(check) > 0 && job.playbook === 'package_preview.yml'" class="btn btn-primary" :disabled="busy" @click="choose(INSTALL)">Install {{ updateLabel(packageCount(check)) }}</button><button v-if="job.status !== 'success' && job.playbook === 'package_preview.yml'" class="btn btn-ghost" :disabled="busy" @click="choose(CHECK)">Check selected devices again</button><router-link :to="{path:'/activity',query:{job:job.job_id}}">View full activity</router-link></div>
          <details v-if="job.output_log" class="output-log"><summary>Technical log</summary><pre>{{ job.output_log }}</pre></details>
        </section>

        <router-link :to="{path:'/access', query:{devices:selectedIds.join(',')}}" class="users-link">Manage users <span>Add or edit accounts in bulk, including CSV imports</span><i class="fas fa-arrow-right" aria-hidden="true"></i></router-link>
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
import HostIpResults from '../components/HostIpResults.vue';
import {visibleStorageOutcomes} from '../utils/storage.js';
import { createRequestKey, getDevices, getOperations, runOperation, getJobs, getJob, getJobProgress } from '../api.js';
import { parseDeviceIds } from '../utils/fleetOverview.js';
import { formatLongTime } from '../utils/time.js';
import { SCAN, IP_CHECK, READINESS, needsScan, CHECK, INSTALL, CLEANUP, REBOOT, STORAGE, GPU, REACHY_RESTART, PLAYBOOKS, ACTION_IDS, ACTIVE, namesFor, sameTargets, validPackageCheck, blockers, packageCount, statusLabel, updateLabel } from '../utils/maintenance.js';


const actions = [
  {id:SCAN,meta:'Facts valid for one hour',cta:'Scan now',completed:'Device scan completed'},
  {id:IP_CHECK,meta:'Works with stale facts',cta:'Find IP',completed:'IP address check completed'},
  {id:READINESS,meta:'Read only',cta:'Check readiness',completed:'Readiness check completed'},
  {id:STORAGE,meta:'Read only',cta:'Check storage',completed:'Storage check completed'},
  {id:GPU,meta:'Read only',cta:'Check GPUs',completed:'GPU check completed'},
  {id:CHECK,meta:'Package preview',cta:'Check now'},
  {id:INSTALL,meta:'Requires a package preview',cta:'Review & install',completed:'Apt updates installed'},
  {id:CLEANUP,meta:'Review before cleanup',cta:'Clear cache…',completed:'Cache cleanup completed'},
  {id:REBOOT,meta:'Interrupts running work',cta:'Reboot…',completed:'Nodes rebooted'},
  {id:REACHY_RESTART,meta:'Reachy Mini daemon',cta:'Restart daemon…',completed:'Reachy Mini daemon restarted'},
];
const route = useRoute(), router = useRouter();
const devices = ref([]), operations = ref([]), selectedIds = ref(parseDeviceIds(route.query.devices || route.query.device));
const loading = ref(true), loadError = ref(''), search = ref(''), starting = ref(''), focused = ref(ACTION_IDS.includes(route.query.operation) ? route.query.operation : ''), confirmation = ref(null), actionError = ref(''), retryRequest = ref(null);
const job = ref(null), check = ref(null), pollError = ref(''), now = ref(Date.now()), resultPanel = ref(null), jobPanel = ref(null), unresolvedNames = ref([]);
const discoverySubnet = ref(''), operationSearch = ref(''), blockedPanel = ref(null), actionErrorPanel = ref(null);
const rolloutMode = ref('parallel'), batchSize = ref(1);
let installAfterCheck = false;
let timer, clockTimer, disposed = false, generation = 0, selectionGeneration = 0, initialized = false;
const selectedDevices = computed(() => devices.value.filter(d => selectedIds.value.includes(d.id)));
const scanRequired = computed(() => selectedDevices.value.filter(d => needsScan(d, now.value)));
const catalog = computed(() => {
  const byId = new Map(operations.value.map(operation => [operation.id, operation]));
  const staleIds = new Set(scanRequired.value.map(device => device.id));
  return actions.filter(action => byId.has(action.id)).map(action => {
    const operation = byId.get(action.id);
    return {...operation, ...action, blocked:blockers(operation, selectedIds.value, devices.value, staleIds)};
  });
});
const visibleActions = computed(() => {
  const query = operationSearch.value.trim().toLowerCase();
  const hasReachyMini = selectedDevices.value.some(device => device.transport === 'reachy_daemon' && device.kind === 'robot' && /^reachy[\s_-]+mini(?:[\s_-]|$)/i.test(device.model || ''));
  return catalog.value.filter(action => (action.id !== REACHY_RESTART || hasReachyMini)
    && `${action.label} ${action.description || ''} ${action.category || ''} ${PLAYBOOKS[action.id]}`.toLowerCase().includes(query));
});
const visibleDevices = computed(() => devices.value.filter(d => `${d.name} ${d.inventory_name} ${d.os_version || ''}`.toLowerCase().includes(search.value.trim().toLowerCase())));
const hiddenSelectionCount = computed(() => {
  const visibleIds = new Set(visibleDevices.value.map(device => device.id));
  return selectedDevices.value.filter(device => !visibleIds.has(device.id)).length;
});
const missingTargets = computed(() => [...unresolvedNames.value, ...selectedIds.value.filter(id => !devices.value.some(d => d.id === id)).map(id => `#${id}`)]);
const jobActive = computed(() => job.value && ACTIVE.includes(job.value.status));
const busy = computed(() => !!starting.value || !!jobActive.value || !!retryRequest.value);
const checkReady = computed(() => !missingTargets.value.length && validPackageCheck(check.value, selectedDevices.value, now.value));
const focusedAction = computed(() => catalog.value.find(action => action.id === focused.value));
const focusedLabel = computed(() => focusedAction.value?.label || 'This action');
const selectionBlockers = computed(() => focusedAction.value?.blocked || []);
const jobAction = computed(() => catalog.value.find(action => PLAYBOOKS[action.id] === job.value?.playbook));
const canChooseRollout = computed(() => confirmation.value && focusedAction.value?.supports_batch_size && selectedDevices.value.length > 1);
const rolling = computed(() => canChooseRollout.value && rolloutMode.value === 'rolling');
const batchSizeValid = computed(() => !rolling.value || (Number.isInteger(batchSize.value) && batchSize.value >= 1 && batchSize.value <= selectedDevices.value.length));
const rolloutSummary = computed(() => {
  const count = selectedDevices.value.length;
  if (!rolling.value) return confirmation.value?.id === REBOOT ? 'Selected nodes can be offline at the same time.' : 'Package installation can run on all selected devices at the same time.';
  if (!batchSizeValid.value) return `Enter a whole number from 1 to ${count}.`;
  const batches = Math.ceil(count / batchSize.value);
  return `${count} devices in ${batches} ${batches === 1 ? 'batch' : 'batches'}, up to ${batchSize.value} at a time.`;
});
const jobHeadline = computed(() => {
  if (jobActive.value && job.value.playbook === 'host_facts.yml') return job.value.status === 'pending' ? 'Scan queued' : 'Scanning devices';
  if (jobActive.value) return job.value.status === 'pending' ? 'Waiting to start…' : ['checking_health','checking_facts'].includes(job.value.phase) ? 'Checking device health' : 'Operation in progress';
  if (job.value.phase === 'health_check_failed') return 'Device health check failed';
  if (job.value.status !== 'success') return job.value.status === 'partial' ? 'Some devices need attention' : 'This operation needs attention';
  if (job.value.playbook === 'package_preview.yml') return packageCount(job.value) ? `${packageCount(job.value)} package ${packageCount(job.value) === 1 ? "update" : "updates"} available` : 'All packages are up to date';
  return jobAction.value?.completed || 'Operation completed';
});
function executionSource(id) {
  if (id === REACHY_RESTART) return 'Reachy daemon';
  if (id === SCAN && selectedDevices.value.some(device => device.transport === 'reachy_daemon')) {
    return selectedDevices.value.some(device => device.transport !== 'reachy_daemon') ? 'host_facts.yml + Reachy daemon' : 'Reachy daemon';
  }
  return PLAYBOOKS[id];
}
function selectVisible() { selectedIds.value = [...new Set([...selectedIds.value, ...visibleDevices.value.map(d => d.id)])]; }
function clearMissing() { selectedIds.value = selectedIds.value.filter(id => devices.value.some(d => d.id === id)); unresolvedNames.value = []; }
const jobProgress = computed(() => ({scanning:'Discovering device hardware, software, health, and supported capabilities. Failed devices remain blocked until a scan succeeds.',checking_health:'Checking services, storage mounts, package health, and detected GPUs after an unfinished operation. Your action will continue automatically.', checking_facts:'Refreshing device details before continuing automatically.', refreshing_facts:'The action finished. Refreshing device details…'})[job.value?.phase] || (job.value?.playbook === 'reboot.yml' ? 'Rebooting selected nodes and waiting for SSH to return on each. You can leave this page and follow progress in Activity.' : job.value?.playbook === REACHY_RESTART ? 'Restarting Reachy Mini daemons one at a time and waiting for the robot backend to be ready. You can follow progress in Activity.' : 'Working on the selected devices. You can leave this page and return to Activity at any time.'));
async function focusPanel(panel) { await nextTick(); panel.value?.focus({preventScroll:true}); panel.value?.scrollIntoView({behavior:'smooth',block:'nearest'}); }
function restoreTargets(names) {
  selectedIds.value = devices.value.filter(device => names.includes(device.inventory_name)).map(device => device.id);
  const inventory = new Set(devices.value.map(device => device.inventory_name));
  unresolvedNames.value = names.filter(name => !inventory.has(name));
}
async function load() {
  loading.value = true; loadError.value = ''; confirmation.value = null;
  try {
    const [allDevices, allOperations] = await Promise.all([getDevices(), getOperations()]);
    if (disposed) return;
    devices.value = allDevices; operations.value = allOperations;
    if (!initialized) {
      initialized = true;
      if (route.query.targets) {
        restoreTargets(namesFor({target_devices:route.query.targets}));
      }
      if (route.query.preview || route.query.job) {
        const restored = await getJob(route.query.job || route.query.preview);
        job.value = restored;
        if (route.query.preview && !route.query.targets && !selectedIds.value.length) restoreTargets(namesFor(restored));
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
  if (!focusedAction.value) return;
  if (selectionBlockers.value.length) {
    await focusPanel(blockedPanel);
    return;
  }
  if ([SCAN, IP_CHECK, READINESS, STORAGE, GPU].includes(id)) {
    await submit(makeRequest(id));
  } else if (id === CHECK || (id === INSTALL && !checkReady.value)) {
    // The installation entry point runs a check first, then opens its package
    // review in place. No background auto-install follows a check.
    await submit(makeRequest(CHECK));
  } else if (id === INSTALL && packageCount(check.value) === 0) {
    job.value = check.value;
  } else {
    await openReview(id);
  }
}
async function openReview(id) {
  rolloutMode.value = 'parallel';
  batchSize.value = 1;
  confirmation.value = {id};
  await focusPanel(resultPanel);
}
function makeRequest(id) {
  const ordered = [...selectedDevices.value].sort((a,b) => a.inventory_name < b.inventory_name ? -1 : a.inventory_name > b.inventory_name ? 1 : 0);
  const parameters = {request_key:createRequestKey(), confirmation:ordered.map(device => device.name).join(', ')};
  if (id === INSTALL) parameters.preview_job_id = check.value.job_id;
  if (id === IP_CHECK) parameters.discovery_subnet = discoverySubnet.value || null;
  if (rolling.value) parameters.batch_size = batchSize.value;
  return {id, ids:[...selectedIds.value], parameters};
}
async function confirmRun() {
  if (!confirmation.value || !focusedAction.value || !batchSizeValid.value || busy.value || loading.value || loadError.value || selectionBlockers.value.length || (confirmation.value.id === INSTALL && !checkReady.value)) return;
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
    await focusPanel(actionErrorPanel);
  } finally { starting.value = ''; }
}
async function pollJob(id) {
  clearTimeout(timer); const current = ++generation;
  try {
    const result = await getJobProgress(id);
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
          await openReview(INSTALL);
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
.main-panel { min-width:0; }.action-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }.action-card { padding:20px; display:flex; flex-direction:column; align-items:flex-start; box-shadow:none; }.action-card.chosen { border-color:var(--focus-ring); }.action-card h4 { line-height:1.4; }.action-card p { font-size:13px; color:var(--text-secondary); line-height:1.6; margin:9px 0 16px; }.action-meta { font-size:11px; color:var(--text-secondary); margin-top:auto; margin-bottom:15px; line-height:1.5; }.action-card .btn { width:100%; min-height:40px; justify-content:center; }.selection-prompt { color:var(--text-secondary); font-size:13px; margin:14px 0; }
.review-panel, .result-panel, .blocked-panel { margin-top:22px; padding:24px; box-shadow:none; }.review-panel { border-color:var(--focus-ring); }.review-panel h3, .result-panel h3 { margin:6px 0 12px; font-size:21px; }.review-panel p, .result-panel p, .blocked-panel p { font-size:13px; line-height:1.6; }.eyebrow { font-size:10px; text-transform:uppercase; letter-spacing:1px; color:var(--text-secondary); }.warning-text { color:var(--status-warning-text); }.muted { color:var(--text-secondary); }.review-actions, .result-actions { display:flex; flex-wrap:wrap; align-items:center; gap:14px; margin-top:20px; }.result-actions a { font-size:13px; }.result-heading { display:flex; justify-content:space-between; gap:16px; align-items:center; }.result-state { padding:6px 10px; border-radius:20px; background:var(--surface-success-soft); font-size:12px; white-space:nowrap; }.result-state.failed { background:var(--surface-warning-soft); }.result-state i { margin-right:6px; }
.outcome { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:8px; padding:12px 0; border-bottom:1px solid var(--border-subtle); font-size:13px; }.outcome p { width:100%; margin:0; color:var(--status-warning-text); overflow-wrap:anywhere; }.install-summary { font-size:13px; padding:12px 0; }.cleanup-summary { margin-top:16px; }.cleanup-summary details { padding:8px 0; }
summary { cursor:pointer; line-height:1.5; }.output-log { border-top:1px solid var(--border-subtle); margin-top:24px; padding-top:16px; font-size:13px; }pre { margin-top:12px; white-space:pre-wrap; overflow-wrap:anywhere; max-height:360px; overflow:auto; padding:14px; background:var(--surface-light); font-size:11px; }
.blocked-device { display:flex; gap:12px; justify-content:space-between; align-items:center; padding:12px 0; border-top:1px solid var(--border-subtle); font-size:13px; }.blocked-device p { margin:4px 0 0; color:var(--text-secondary); }.blocked-actions { display:flex; gap:12px; align-items:center; flex-shrink:0; }.action-error { margin-top:20px; }.loading-state { padding:60px 0; text-align:center; color:var(--text-secondary); }
@media(max-width:1150px) { .workspace { grid-template-columns:250px minmax(0,1fr); gap:16px; }.action-grid { grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }.action-card { padding:16px; }.action-card h4 { font-size:14px; }.blocked-device { align-items:flex-start; flex-direction:column; } }
@media(max-width:900px) { .workspace { grid-template-columns:1fr; }.devices-panel { position:static; }.device-list { max-height:240px; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); }.panel-heading { padding-bottom:12px; }.selection-tools { display:flex; gap:20px; align-items:center; }.selection-tools input { flex:1; min-width:0; }.selection-tools > div { gap:16px; padding:0; }.action-card { padding:20px; } }
@media(max-width:580px) { .action-grid { grid-template-columns:1fr; }.device-list { grid-template-columns:1fr; }.selection-tools { display:block; }.selection-tools > div { padding-top:8px; }.review-panel,.result-panel,.blocked-panel { padding:18px; }.result-heading { align-items:flex-start; flex-direction:column; gap:0; } }
.catalog-tools, .rollout-fields { display:flex; flex-wrap:wrap; align-items:center; gap:12px; }
.catalog-tools { justify-content:space-between; margin-bottom:14px; }
.review-panel, .blocked-panel { margin:0 0 20px; scroll-margin-top:90px; }
.subnet-options { margin:0 0 14px; font-size:13px; width:100%; }
.subnet-options summary { color:var(--link-text); }
.subnet-options label { display:block; margin:8px 0 4px; }
.subnet-options small { display:block; color:var(--text-secondary); margin-top:5px; }
.catalog-search { flex:0 1 290px; }
.action-card h4 { margin:0; font-size:16px; }
.playbook-name { font-family:var(--font-mono, monospace); font-size:12px; overflow-wrap:anywhere; color:var(--text-secondary); margin-top:4px; }
.action-blockers { font-size:12px; color:var(--status-warning-text); margin-bottom:8px; }
.no-matches { padding:20px 0; color:var(--text-secondary); }
.review-targets { font-size:13px; }
.review-targets ul { display:flex; flex-wrap:wrap; gap:6px 14px; list-style:none; margin:6px 0; padding:0; max-height:10rem; overflow:auto; }
.review-targets li { overflow-wrap:anywhere; }
.review-targets code { color:var(--text-secondary); }
.rollout-options { border:0; border-top:1px solid var(--border-subtle); margin:16px 0 0; padding:8px 0 0; min-width:0; }
.rollout-options legend { font-size:14px; font-weight:600; padding-right:8px; }
.rollout-fields label { display:grid; gap:4px; font-size:12px; }
.rollout-fields input { width:9em; }
.rollout-options p { margin:8px 0; }
@media(max-width:580px) { .catalog-search { flex-basis:100%; }.review-panel, .blocked-panel { scroll-margin-top:120px; } }
</style>
