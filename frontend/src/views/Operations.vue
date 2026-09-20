<template>
  <div>
    <div class="page-header"><div><h2>Operations</h2><p class="page-subtitle">Choose an action and review its eligible targets. Blocked devices include a reason.</p></div><button class="btn btn-ghost btn-sm" :disabled="loading" @click="load"><i :class="['fas', loading ? 'fa-spinner fa-spin' : 'fa-sync-alt']" aria-hidden="true"></i>Refresh</button></div>
    <div v-if="operations.length" class="operation-layout">
      <aside class="target-panel card">
        <div class="card-body"><span class="eyebrow">Target</span><h3>{{ targetSummary }}</h3><p>Selections apply to the operation you run.</p><button class="btn btn-ghost btn-sm" @click="selectAllVisible">Select eligible</button><button class="btn btn-ghost btn-sm" :disabled="!selectedIds.length" @click="selectedIds = []">Clear</button></div>
      </aside>
      <main>
        <section v-for="group in groupedOperations" :key="group.category" class="operation-group">
          <h3>{{ group.category }}</h3>
          <div class="operation-grid">
            <article v-for="operation in group.items" :key="operation.id" :id="`operation-${operation.id.replaceAll('.', '-')}`" class="card operation-card">
              <div class="card-body">
                <div class="operation-header"><span class="operation-icon" aria-hidden="true"><i :class="['fas', operation.icon]"></i></span><span :class="['impact', `impact-${operation.risk}`]">{{ operation.risk }} impact</span></div>
                <h4>{{ operation.label }}</h4><p>{{ operation.description }}</p>
                <div class="eligible-list">
                  <label v-for="device in eligibleDevices(operation)" :key="device.id" class="checkbox-label"><input v-model="selectedIds" type="checkbox" :value="device.id" /><span>{{ device.name }}</span><small>{{ deviceKind(device.kind).short }}</small></label>
                </div>
                <details v-if="operation.excluded_devices?.length" class="excluded"><summary>{{ operation.excluded_devices.length }} unavailable devices</summary><p v-for="device in operation.excluded_devices" :key="device.id"><router-link :to="`/devices/${device.id}`">{{ device.name }}</router-link>: {{ device.reason }}</p></details>
                <div v-if="operation.id === 'services.manage'" class="operation-params"><label for="service-unit">Existing service unit</label><input id="service-unit" v-model.trim="serviceName" class="form-input" placeholder="nginx.service" /><label for="service-action">Action</label><select id="service-action" v-model="serviceAction" class="form-select"><option value="started">Start</option><option value="stopped">Stop</option><option value="restarted">Restart</option></select><p>Run Inspect services to review unit names and state first.</p></div>
                <div v-if="operation.id === 'system.update'" class="operation-params"><label for="package-preview">Reviewed package preview</label><select id="package-preview" v-model="previewId" class="form-select" @change="previewReviewed = false"><option value="">Choose a preview for these exact devices</option><option v-for="preview in matchingPreviews" :key="preview.job_id" :value="preview.job_id">{{ formatLongTime(preview.finished_at) }} · {{ preview.target_devices }}</option></select><p v-if="!matchingPreviews.length">Run Preview package updates first. Previews expire after 30 minutes.</p><router-link v-if="previewId" :to="`/activity?job=${previewId}`">Review proposed package changes</router-link><label v-if="previewId" class="checkbox-label"><input v-model="previewReviewed" type="checkbox" />I reviewed these package changes</label></div>
                <button class="btn btn-primary btn-sm operation-run" :disabled="!selectedFor(operation).length || !!running || !parametersReady(operation)" @click="askRun(operation)"><i :class="['fas', running === operation.id ? 'fa-spinner fa-spin' : operation.icon]" aria-hidden="true"></i>{{ running === operation.id ? 'Starting…' : selectedFor(operation).length ? `Run on ${selectedFor(operation).length}` : 'Select devices' }}</button>
              </div>
            </article>
          </div>
        </section>
      </main>
    </div>
    <div v-else-if="!loading" class="empty-state"><i class="fas fa-bolt" aria-hidden="true"></i><p>No operations are available until a device is added and discovered.</p><router-link to="/devices?add=1" class="btn btn-primary btn-sm">Add device</router-link></div>
    <ConfirmDialog :visible="confirm.show" :title="confirm.title" :message="confirm.message" :confirm-text="confirm.confirmText" :danger-mode="confirm.danger" danger-label="Disruptive action" :require-text="confirm.requireText" @confirm="runConfirmed" @cancel="confirm.show = false" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getDevices, getOperations, runOperation, getJobs } from "../api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import { deviceKind } from "../utils/devices.js";
import { selectedOperationTargets } from "../utils/operations.js";
import { exactPreviewTargets } from "../utils/access.js";
import { formatLongTime } from "../utils/time.js";
const previews = ref([]), previewId = ref(""), previewReviewed = ref(false), serviceName = ref(""), serviceAction = ref("restarted");
const matchingPreviews = computed(() => previews.value.filter(job => exactPreviewTargets(job, devices.value, selectedIds.value)));
function parametersReady(op) { return op.id === "system.update" ? previewReviewed.value && matchingPreviews.value.some(p => p.job_id === previewId.value) : op.id === "services.manage" ? /^[A-Za-z0-9][A-Za-z0-9_.@:-]{0,120}\.service$/.test(serviceName.value) : true; }
const router = useRouter();
const route = useRoute(); const devices = ref([]); const operations = ref([]); const loading = ref(true); const running = ref(""); const selectedIds = ref(route.query.device ? [Number(route.query.device)] : []); const pending = ref(null); const confirm = ref({ show: false, title: "", message: "", confirmText: "Run", danger: false, requireText: "" });
watch(selectedIds, () => { previewReviewed.value = false; }, {deep:true});
const groupedOperations = computed(() => { const groups = []; operations.value.forEach((operation) => { let group = groups.find((item) => item.category === operation.category); if (!group) { group = { category: operation.category, items: [] }; groups.push(group); } group.items.push(operation); }); return groups; });
const targetSummary = computed(() => selectedIds.value.length ? `${selectedIds.value.length} selected` : "Choose devices");
function eligibleDevices(operation) { return devices.value.filter((device) => operation.eligible_device_ids.includes(device.id)); }
function selectedFor(operation) { return selectedOperationTargets(operation, selectedIds.value); }
function selectAllVisible() { selectedIds.value = [...new Set(operations.value.flatMap((operation) => operation.eligible_device_ids))]; }
async function load() { loading.value = true; try { [devices.value, operations.value, previews.value] = await Promise.all([getDevices(), getOperations(), getJobs({playbook:"package_preview.yml", status:"success", limit:200})]); if (route.query.preview) { const preview = previews.value.find(p => p.job_id === route.query.preview); if (preview) { selectedIds.value = devices.value.filter(d => preview.target_devices.split(",").includes(d.inventory_name)).map(d => d.id); previewId.value = preview.job_id; } } } catch (error) { window.$toast?.error("Couldn't load operations", error); } finally { loading.value = false; } }
function askRun(operation) { const ids = selectedFor(operation); if (!ids.length || running.value || !parametersReady(operation)) return; const names = devices.value.filter((device) => ids.includes(device.id)).sort((a,b) => (a.inventory_name < b.inventory_name ? -1 : a.inventory_name > b.inventory_name ? 1 : 0)).map((device) => device.name); const parameters = {request_key:crypto.randomUUID(), confirmation:names.join(", ")}; if (operation.id === "system.update") parameters.preview_job_id = previewId.value; if (operation.id === "services.manage") Object.assign(parameters, {service_name:serviceName.value, service_action:serviceAction.value}); pending.value = { operation, ids, parameters }; confirm.value = { show: true, title: operation.label, message: `${operation.description} ${operation.id === "services.manage" ? `${({started:"Start",stopped:"Stop",restarted:"Restart"})[serviceAction.value]} ${serviceName.value}.` : ""} Target ${ids.length} device${ids.length === 1 ? '' : 's'}: ${names.join(', ')}.`, confirmText: operation.label, danger: operation.risk === "high", requireText: operation.confirmation === "typed-target" ? names.join(", ") : "" }; }
async function runConfirmed() { if (!pending.value || running.value) return; confirm.value.show = false; const { operation, ids, parameters } = pending.value; running.value = operation.id; try { const result = await runOperation(operation.id, ids, parameters); window.$toast?.success(result.detail || `${operation.label} started`); if (result.job_id) await router.push({ path: '/activity', query: { job: result.job_id } }); } catch (error) { window.$toast?.error(`Couldn't start ${operation.label.toLowerCase()}`, error); confirm.value.show = true; } finally { running.value = ""; } }
onMounted(async () => { await load(); if (route.query.preview) { await nextTick(); document.getElementById("operation-system-update")?.scrollIntoView({block:"center"}); } });
</script>

<style scoped>
.excluded { margin-bottom:14px; font-size:12px; }.excluded p { margin:8px 0; min-height:0; }.operation-params { display:grid; gap:8px; margin-bottom:14px; font-size:12px; }.operation-params p { min-height:0; }summary { cursor:pointer; }.page-subtitle { margin: 4px 0 0; color: var(--text-secondary); }.operation-layout { display: grid; grid-template-columns: 220px 1fr; gap: 18px; align-items: start; }.target-panel { position: sticky; top: 82px; }.target-panel h3 { margin: 4px 0; }.target-panel p { color: var(--text-secondary); font-size: 12px; }.target-panel .btn { width: 100%; margin-top: 8px; }.eyebrow { font-size: 10px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .7px; }.operation-group { margin-bottom: 22px; }.operation-group > h3 { margin: 0 0 10px; }.operation-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(285px, 1fr)); gap: 12px; }.operation-card .card-body { height: 100%; display: flex; flex-direction: column; }.operation-header { display: flex; align-items: center; justify-content: space-between; }.operation-icon { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 10px; color: var(--color-accent); background: var(--surface-info-soft); }.impact { padding: 4px 7px; border-radius: 12px; font-size: 10px; text-transform: uppercase; }.impact-low { background: var(--surface-success-soft); color: var(--text-primary); }.impact-medium { background: var(--surface-warning-soft); color: var(--text-primary); }.impact-high { background: var(--surface-danger-soft); color: var(--color-danger); }.operation-card h4 { margin: 13px 0 5px; }.operation-card p { margin: 0 0 12px; color: var(--text-secondary); font-size: 12px; min-height: 34px; }.eligible-list { max-height: 145px; overflow: auto; padding: 8px; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); margin-bottom: 12px; }.eligible-list .checkbox-label { padding: 5px 3px; }.eligible-list .checkbox-label span { flex: 1; overflow: hidden; text-overflow: ellipsis; }.eligible-list small { color: var(--text-secondary); }.operation-run { margin-top: auto; width: 100%; }
@media (max-width: 760px) { .operation-layout { grid-template-columns: 1fr; }.target-panel { position: static; }.operation-grid { grid-template-columns: 1fr; } }
</style>
