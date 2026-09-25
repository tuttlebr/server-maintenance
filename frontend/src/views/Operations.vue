<template>
  <div>
    <div class="page-header"><div><h2>Operations</h2><p class="page-subtitle">Choose an action and review its eligible targets. Blocked devices include a reason.</p></div><button class="btn btn-ghost btn-sm" :disabled="loading" @click="load"><i :class="['fas', loading ? 'fa-spinner fa-spin' : 'fa-sync-alt']" aria-hidden="true"></i>Refresh</button></div>
    <p v-if="route.query.reason" class="operation-origin"><router-link to="/">Overview</router-link> / {{ reasonLabel }}</p>
    <div v-if="loadError" class="callout callout-danger" role="alert">Operations could not be refreshed. Target eligibility must be refreshed before starting work.</div>
    <div class="operation-filter">
      <label for="operation-filter">Operation (A–Z)</label>
      <div class="operation-picker">
        <select id="operation-filter" v-model="operationFilter" class="form-select" :aria-describedby="focusedOperation ? 'operation-hint' : undefined">
          <option value="">Browse all operations</option>
          <option v-for="operation in operationOptions" :key="operation.id" :value="operation.id">{{ operationOptionLabel(operation) }}</option>
          <option v-if="operationFilter && !focusedOperation" :value="operationFilter">Requested operation unavailable</option>
        </select>
        <p v-if="focusedOperation" id="operation-hint" class="operation-hint">{{ focusedOperation.description }}</p>
      </div>
      <router-link v-if="scopeRequested" :to="{ path: '/operations' }">Clear target scope and browse catalog</router-link>
    </div>
    <div v-if="unmatchedTargets.length" class="callout callout-warn"><div>These job targets could not be matched to current devices: {{ unmatchedTargets.join(', ') }}. Review the remaining names before proceeding.<button class="btn btn-ghost btn-sm" @click="useMatchedTargets">Use only matched devices</button></div></div>
    <div v-if="operationFilter && !focusedOperation && !loading && !loadError" class="callout callout-warn">This operation is not available for the discovered fleet. <router-link to="/devices">Review device capabilities</router-link>.</div>
    <div v-if="operations.length" class="operation-layout">
      <aside class="target-panel card">
        <div class="card-body"><span class="eyebrow">Target scope</span><h3>{{ targetSummary }}</h3><p>{{ scopeRequested ? 'Only devices passed into this review are included.' : 'Selections apply to the operation you run.' }}</p><ul class="selected-targets"><li v-for="id in selectedIds" :key="id"><strong>{{ devices.find(device => device.id === id)?.name || `Unavailable device #${id}` }}</strong><span v-if="focusedOperation">{{ targetEligibility(id) }}</span><button class="target-remove" :aria-label="`Remove ${devices.find(device => device.id === id)?.name || id} from selection`" @click="selectedIds = selectedIds.filter(value => value !== id)">Remove</button></li></ul><p v-if="focusedOperation">In your selection: {{ selectedFor(focusedOperation).length }} eligible · {{ selectedIds.length - selectedFor(focusedOperation).length }} excluded</p><button v-if="focusedOperation" class="btn btn-ghost btn-sm" @click="selectAllVisible">Select eligible in this scope</button><button class="btn btn-ghost btn-sm" :disabled="!selectedIds.length" @click="selectedIds = []">Clear selection</button></div>
      </aside>
      <div class="operation-catalog">
        <section v-for="group in groupedOperations" :key="group.category" class="operation-group">
          <h3>{{ group.category }}</h3>
          <div class="operation-grid">
            <article v-for="operation in group.items" :key="operation.id" :id="`operation-${operation.id.replaceAll('.', '-')}`" class="card operation-card">
              <div class="card-body">
                <div class="operation-header"><span class="operation-icon" aria-hidden="true"><i :class="['fas', operation.icon]"></i></span><span :class="['impact', `impact-${operation.risk}`]">{{ operation.risk }} impact</span></div>
                <h4>{{ operation.label }}</h4><p>{{ operation.description }}</p>
                <p>{{ eligibleDevices(operation).length }} eligible in scope · {{ excludedDevices(operation).length }} excluded</p><div class="eligible-list">
                  <label v-for="device in eligibleDevices(operation)" :key="device.id" class="checkbox-label"><input v-model="selectedIds" type="checkbox" :value="device.id" /><span>{{ device.name }}</span><small>{{ deviceKind(device.kind).short }}</small></label>
                </div>
                <details v-if="excludedDevices(operation).length" class="excluded"><summary>{{ excludedDevices(operation).length }} unavailable {{ excludedDevices(operation).length === 1 ? 'device' : 'devices' }}</summary><p v-for="device in excludedDevices(operation)" :key="device.id"><router-link :to="`/devices/${device.id}`">{{ device.name }}</router-link>: {{ device.reason }}</p></details>
                <div v-if="operation.id === 'services.manage'" class="operation-params"><label for="service-unit">Existing service unit</label><input id="service-unit" v-model.trim="serviceName" class="form-input" placeholder="nginx.service" /><label for="service-action">Action</label><select id="service-action" v-model="serviceAction" class="form-select"><option value="started">Start</option><option value="stopped">Stop</option><option value="restarted">Restart</option></select><p>Run Inspect services to review unit names and state first.</p></div>
                <div v-if="operation.id === 'system.update'" class="operation-params"><label for="package-preview">Reviewed package preview</label><select id="package-preview" v-model="previewId" class="form-select" @change="previewReviewed = false"><option value="">Choose a preview for these exact devices</option><option v-for="preview in matchingPreviews" :key="preview.job_id" :value="preview.job_id">{{ formatLongTime(preview.finished_at) }} · {{ preview.target_devices }}</option></select><p v-if="!matchingPreviews.length">Run Preview package updates first. Previews expire after 30 minutes.</p><router-link v-if="previewId" :to="`/activity?job=${previewId}`">Review proposed package changes</router-link><label v-if="previewId" class="checkbox-label"><input v-model="previewReviewed" type="checkbox" />I reviewed these package changes</label></div>
                <p v-if="selectedIds.length && selectedFor(operation).length !== selectedIds.length" class="scope-warning">{{ selectedIds.length - selectedFor(operation).length }} excluded from this selection. Confirmation includes {{ selectedFor(operation).length }} eligible {{ selectedFor(operation).length === 1 ? 'target' : 'targets' }}.</p><button class="btn btn-primary btn-sm operation-run" :disabled="!selectedFor(operation).length || !!running || !parametersReady(operation)" @click="askRun(operation)"><i :class="['fas', running === operation.id ? 'fa-spinner fa-spin' : operation.icon]" aria-hidden="true"></i>{{ running === operation.id ? 'Starting…' : selectedFor(operation).length ? `Run on ${selectedFor(operation).length}` : 'Select devices' }}</button>
              </div>
            </article>
          </div>
        </section>
      </div>
    </div>
    <div v-else-if="!loading && !loadError && !operationFilter" class="empty-state"><i class="fas fa-bolt" aria-hidden="true"></i><p>No operations are available until a device is added and discovered.</p><router-link to="/devices?add=1" class="btn btn-primary btn-sm">Add device</router-link></div>
    <ConfirmDialog :visible="confirm.show" :title="confirm.title" :message="confirm.message" :confirm-text="confirm.confirmText" :danger-mode="confirm.danger" danger-label="Disruptive action" :require-text="confirm.requireText" @confirm="runConfirmed" @cancel="confirm.show = false" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getDevices, getOperations, runOperation, getJobs } from "../api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import { deviceKind } from "../utils/devices.js";
import { ATTENTION_GROUPS, parseDeviceIds, targetNames } from "../utils/fleetOverview.js";
import { operationOptionLabel, selectedOperationTargets, sortOperationsByLabel } from "../utils/operations.js";
import { exactPreviewTargets } from "../utils/access.js";
import { formatLongTime } from "../utils/time.js";
const previews = ref([]), previewId = ref(""), previewReviewed = ref(false), serviceName = ref(""), serviceAction = ref("restarted");
const matchingPreviews = computed(() => previews.value.filter(job => exactPreviewTargets(job, devices.value, selectedIds.value)));
function parametersReady(op) { if (loading.value || loadError.value || unmatchedTargets.value.length || selectedIds.value.some(id => !devices.value.some(device => device.id === id))) return false; return op.id === "system.update" ? previewReviewed.value && matchingPreviews.value.some(p => p.job_id === previewId.value) : op.id === "services.manage" ? /^[A-Za-z0-9][A-Za-z0-9_.@:-]{0,120}\.service$/.test(serviceName.value) : true; }
const router = useRouter();
const route = useRoute(); const devices = ref([]); const operations = ref([]); const loading = ref(true); const loadError = ref(null); const running = ref(""); const selectedIds = ref(parseDeviceIds(route.query.devices || route.query.device)); const pending = ref(null); const confirm = ref({ show: false, title: "", message: "", confirmText: "Run", danger: false, requireText: "" });
watch(selectedIds, () => { previewReviewed.value = false; }, {deep:true});
const groupedOperations = computed(() => { const groups = []; visibleOperations.value.forEach((operation) => { let group = groups.find((item) => item.category === operation.category); if (!group) { group = { category: operation.category, items: [] }; groups.push(group); } group.items.push(operation); }); return groups; });
const targetSummary = computed(() => selectedIds.value.length ? `${selectedIds.value.length} selected` : "Choose devices");
const operationFilter = computed({ get: () => String(route.query.operation || (route.query.preview ? 'system.update' : '')), set: operation => router.replace({ query: { ...route.query, operation: operation || undefined, preview: undefined } }) });
const focusedOperation = computed(() => operations.value.find(operation => operation.id === operationFilter.value));
const operationOptions = computed(() => sortOperationsByLabel(operations.value));
const visibleOperations = computed(() => operationFilter.value ? operations.value.filter(operation => operation.id === operationFilter.value) : operations.value);
const scopeRequested = computed(() => route.query.devices !== undefined || route.query.device !== undefined || route.query.targets !== undefined);
const requestedNames = computed(() => targetNames({ target_devices: route.query.targets }));
const unmatchedTargets = computed(() => requestedNames.value.filter(name => !devices.value.some(device => device.inventory_name === name)));
const scopeIds = computed(() => route.query.targets !== undefined ? devices.value.filter(device => requestedNames.value.includes(device.inventory_name)).map(device => device.id) : parseDeviceIds(route.query.devices ?? route.query.device));
const reasonLabel = computed(() => ATTENTION_GROUPS.find(group => group.id === route.query.reason)?.label || 'Target review');
function applyRouteTargets() { selectedIds.value = [...scopeIds.value]; }
function useMatchedTargets() { router.replace({ query: { ...route.query, devices: scopeIds.value.join(','), device: undefined, targets: undefined } }); }
function eligibleDevices(operation) { return devices.value.filter(device => operation.eligible_device_ids.includes(device.id) && (!scopeRequested.value || scopeIds.value.includes(device.id))); }
function excludedDevices(operation) { return (operation.excluded_devices || []).filter(device => !scopeRequested.value || scopeIds.value.includes(device.id)); }
function selectedFor(operation) { return selectedOperationTargets(operation, selectedIds.value); }
function targetEligibility(id) { return focusedOperation.value?.eligible_device_ids.includes(id) ? 'Eligible' : focusedOperation.value?.excluded_devices?.find(device => device.id === id)?.reason || 'Not available in the latest observation'; }
function selectAllVisible() { if (focusedOperation.value) selectedIds.value = eligibleDevices(focusedOperation.value).map(device => device.id); }
async function load() {
  loading.value = true;
  try {
    [devices.value, operations.value, previews.value] = await Promise.all([getDevices(), getOperations(), getJobs({playbook:'package_preview.yml', status:'success', limit:200})]);
    loadError.value = null;
    if (!initialized) { applyRouteTargets(); initialized = true; }
    if (route.query.preview) {
      const preview = previews.value.find(job => job.job_id === route.query.preview);
      if (preview) { selectedIds.value = devices.value.filter(device => targetNames(preview).includes(device.inventory_name)).map(device => device.id); previewId.value = preview.job_id; }
    }
  } catch (error) { loadError.value = error; window.$toast?.error("Couldn't load operations", error); }
  finally { loading.value = false; }
}
let initialized = false;
watch(() => [route.query.devices, route.query.device, route.query.targets].join('|'), applyRouteTargets);
function askRun(operation) { const ids = selectedFor(operation); if (!ids.length || running.value || !parametersReady(operation)) return; const names = devices.value.filter((device) => ids.includes(device.id)).sort((a,b) => (a.inventory_name < b.inventory_name ? -1 : a.inventory_name > b.inventory_name ? 1 : 0)).map((device) => device.name); const parameters = {request_key:crypto.randomUUID(), confirmation:names.join(", ")}; if (operation.id === "system.update") parameters.preview_job_id = previewId.value; if (operation.id === "services.manage") Object.assign(parameters, {service_name:serviceName.value, service_action:serviceAction.value}); pending.value = { operation, ids, parameters }; confirm.value = { show: true, title: operation.label, message: `${operation.description} ${operation.id === "services.manage" ? `${({started:"Start",stopped:"Stop",restarted:"Restart"})[serviceAction.value]} ${serviceName.value}.` : ""} Target ${ids.length} device${ids.length === 1 ? '' : 's'}: ${names.join(', ')}.`, confirmText: operation.label, danger: operation.risk === "high", requireText: operation.confirmation === "typed-target" || operation.risk !== "low" ? names.join(", ") : "" }; }
async function runConfirmed() { if (!pending.value || running.value) return; confirm.value.show = false; const { operation, ids, parameters } = pending.value; running.value = operation.id; try { const result = await runOperation(operation.id, ids, parameters); window.$toast?.success(result.detail || `${operation.label} started`); if (result.job_id) await router.push({ path: '/activity', query: { job: result.job_id } }); } catch (error) { window.$toast?.error(`Couldn't start ${operation.label.toLowerCase()}`, error); confirm.value.show = true; } finally { running.value = ""; } }
onMounted(async () => { await load(); if (route.query.preview) { await nextTick(); document.getElementById("operation-system-update")?.scrollIntoView({block:"center"}); } });
</script>

<style scoped>
.operation-picker { flex: 1 1 320px; min-width: 0; max-width: 640px; }
.operation-filter .operation-picker select { width: 100%; }
.operation-hint { margin: 6px 0 0; color: var(--text-secondary); font-size: 12px; line-height: 1.5; }
.operation-origin { margin-bottom: 14px; color: var(--text-secondary); font-size: 13px; }.operation-filter { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 18px; }.operation-filter select { width: min(100%, 360px); }.operation-filter label { font-size: 13px; font-weight: 650; }.selected-targets { list-style: none; max-height: 330px; overflow-y: auto; margin: 12px 0; }.selected-targets li { display: grid; gap: 4px; padding: 10px 0; border-bottom: 1px solid var(--border-subtle); font-size: 12px; overflow-wrap: anywhere; }.selected-targets span { color: var(--text-secondary); }.target-remove { color: var(--link-text); background: none; border: 0; padding: 2px 0; width: fit-content; font: inherit; cursor: pointer; }.scope-warning { color: var(--status-warning-text) !important; font-size: 12px; }.operation-catalog { min-width: 0; }

.excluded { margin-bottom:14px; font-size:12px; }.excluded p { margin:8px 0; min-height:0; }.operation-params { display:grid; gap:8px; margin-bottom:14px; font-size:12px; }.operation-params p { min-height:0; }summary { cursor:pointer; }.page-subtitle { margin: 4px 0 0; color: var(--text-secondary); }.operation-layout { display: grid; grid-template-columns: 220px 1fr; gap: 18px; align-items: start; }.target-panel { position: sticky; top: 82px; }.target-panel h3 { margin: 4px 0; }.target-panel p { color: var(--text-secondary); font-size: 12px; }.target-panel .btn { width: 100%; margin-top: 8px; }.eyebrow { font-size: 10px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .7px; }.operation-group { margin-bottom: 22px; }.operation-group > h3 { margin: 0 0 10px; }.operation-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(285px, 1fr)); gap: 12px; }.operation-card .card-body { height: 100%; display: flex; flex-direction: column; }.operation-header { display: flex; align-items: center; justify-content: space-between; }.operation-icon { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 10px; color: var(--color-accent); background: var(--surface-info-soft); }.impact { padding: 4px 7px; border-radius: 12px; font-size: 10px; text-transform: uppercase; }.impact-low { background: var(--surface-success-soft); color: var(--text-primary); }.impact-medium { background: var(--surface-warning-soft); color: var(--text-primary); }.impact-high { background: var(--surface-danger-soft); color: var(--status-danger-text); }.operation-card h4 { margin: 13px 0 5px; }.operation-card p { margin: 0 0 12px; color: var(--text-secondary); font-size: 12px; min-height: 34px; }.eligible-list { max-height: 145px; overflow: auto; padding: 8px; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); margin-bottom: 12px; }.eligible-list .checkbox-label { padding: 5px 3px; }.eligible-list .checkbox-label span { flex: 1; overflow: hidden; text-overflow: ellipsis; }.eligible-list small { color: var(--text-secondary); }.operation-run { margin-top: auto; width: 100%; }
@media (max-width: 760px) { .operation-layout { grid-template-columns: 1fr; }.target-panel { position: static; }.operation-grid { grid-template-columns: 1fr; } }
</style>
