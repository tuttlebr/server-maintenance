<template>
  <div>
    <div class="page-header"><div><h2>Operations</h2><p class="page-subtitle">Only actions supported by the current fleet are shown.</p></div><button class="btn btn-ghost btn-sm" :disabled="loading" @click="load"><i :class="['fas', loading ? 'fa-spinner fa-spin' : 'fa-sync-alt']" aria-hidden="true"></i>Refresh</button></div>
    <div v-if="operations.length" class="operation-layout">
      <aside class="target-panel card">
        <div class="card-body"><span class="eyebrow">Target</span><h3>{{ targetSummary }}</h3><p>Selections apply to the operation you run.</p><button class="btn btn-ghost btn-sm" @click="selectAllVisible">Select eligible</button><button class="btn btn-ghost btn-sm" :disabled="!selectedIds.length" @click="selectedIds = []">Clear</button></div>
      </aside>
      <main>
        <section v-for="group in groupedOperations" :key="group.category" class="operation-group">
          <h3>{{ group.category }}</h3>
          <div class="operation-grid">
            <article v-for="operation in group.items" :key="operation.id" class="card operation-card">
              <div class="card-body">
                <div class="operation-header"><span class="operation-icon" aria-hidden="true"><i :class="['fas', operation.icon]"></i></span><span :class="['impact', `impact-${operation.risk}`]">{{ operation.risk }} impact</span></div>
                <h4>{{ operation.label }}</h4><p>{{ operation.description }}</p>
                <div class="eligible-list">
                  <label v-for="device in eligibleDevices(operation)" :key="device.id" class="checkbox-label"><input v-model="selectedIds" type="checkbox" :value="device.id" /><span>{{ device.name }}</span><small>{{ deviceKind(device.kind).short }}</small></label>
                </div>
                <button class="btn btn-primary btn-sm operation-run" :disabled="!selectedFor(operation).length || running === operation.id" @click="askRun(operation)"><i :class="['fas', running === operation.id ? 'fa-spinner fa-spin' : operation.icon]" aria-hidden="true"></i>{{ running === operation.id ? 'Starting…' : `Run on ${selectedFor(operation).length || operation.eligible_count}` }}</button>
              </div>
            </article>
          </div>
        </section>
      </main>
    </div>
    <div v-else-if="!loading" class="empty-state"><i class="fas fa-bolt" aria-hidden="true"></i><p>No operations are available until a device is added and discovered.</p><router-link to="/devices?add=1" class="btn btn-primary btn-sm">Add device</router-link></div>
    <ConfirmDialog :visible="confirm.show" :title="confirm.title" :message="confirm.message" :confirm-text="confirm.confirmText" :danger-mode="confirm.danger" :require-text="confirm.requireText" @confirm="runConfirmed" @cancel="confirm.show = false" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { getDevices, getOperations, runOperation } from "../api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import { deviceKind } from "../utils/devices.js";
const route = useRoute(); const devices = ref([]); const operations = ref([]); const loading = ref(true); const running = ref(""); const selectedIds = ref(route.query.device ? [Number(route.query.device)] : []); const pending = ref(null); const confirm = ref({ show: false, title: "", message: "", confirmText: "Run", danger: false, requireText: "" });
const groupedOperations = computed(() => { const groups = []; operations.value.forEach((operation) => { let group = groups.find((item) => item.category === operation.category); if (!group) { group = { category: operation.category, items: [] }; groups.push(group); } group.items.push(operation); }); return groups; });
const targetSummary = computed(() => selectedIds.value.length ? `${selectedIds.value.length} selected` : "Choose devices");
function eligibleDevices(operation) { return devices.value.filter((device) => operation.eligible_device_ids.includes(device.id)); }
function selectedFor(operation) { const selected = selectedIds.value.filter((id) => operation.eligible_device_ids.includes(id)); return selected.length ? selected : (selectedIds.value.length ? [] : operation.eligible_device_ids); }
function selectAllVisible() { selectedIds.value = [...new Set(operations.value.flatMap((operation) => operation.eligible_device_ids))]; }
async function load() { loading.value = true; try { [devices.value, operations.value] = await Promise.all([getDevices(), getOperations()]); } catch (error) { window.$toast?.error("Couldn't load operations", error); } finally { loading.value = false; } }
function askRun(operation) { const ids = selectedFor(operation); const names = devices.value.filter((device) => ids.includes(device.id)).map((device) => device.name); pending.value = { operation, ids }; confirm.value = { show: true, title: operation.label, message: `${operation.description} Target ${ids.length} device${ids.length === 1 ? '' : 's'}: ${names.join(', ')}.`, confirmText: operation.label, danger: operation.risk === "high", requireText: operation.confirmation === "typed-target" ? names.join(", ") : "" }; }
async function runConfirmed() { confirm.value.show = false; const { operation, ids } = pending.value; running.value = operation.id; try { const result = await runOperation(operation.id, ids); window.$toast?.success(result.detail || `${operation.label} started`); } catch (error) { window.$toast?.error(`Couldn't start ${operation.label.toLowerCase()}`, error); } finally { running.value = ""; pending.value = null; } }
onMounted(load);
</script>

<style scoped>
.page-subtitle { margin: 4px 0 0; color: var(--text-secondary); }.operation-layout { display: grid; grid-template-columns: 220px 1fr; gap: 18px; align-items: start; }.target-panel { position: sticky; top: 82px; }.target-panel h3 { margin: 4px 0; }.target-panel p { color: var(--text-secondary); font-size: 12px; }.target-panel .btn { width: 100%; margin-top: 8px; }.eyebrow { font-size: 10px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .7px; }.operation-group { margin-bottom: 22px; }.operation-group > h3 { margin: 0 0 10px; }.operation-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(285px, 1fr)); gap: 12px; }.operation-card .card-body { height: 100%; display: flex; flex-direction: column; }.operation-header { display: flex; align-items: center; justify-content: space-between; }.operation-icon { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 10px; color: var(--color-accent); background: var(--surface-info-soft); }.impact { padding: 4px 7px; border-radius: 12px; font-size: 10px; text-transform: uppercase; }.impact-low { background: var(--surface-success-soft); color: var(--text-primary); }.impact-medium { background: var(--surface-warning-soft); color: var(--text-primary); }.impact-high { background: var(--surface-danger-soft); color: var(--color-danger); }.operation-card h4 { margin: 13px 0 5px; }.operation-card p { margin: 0 0 12px; color: var(--text-secondary); font-size: 12px; min-height: 34px; }.eligible-list { max-height: 145px; overflow: auto; padding: 8px; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); margin-bottom: 12px; }.eligible-list .checkbox-label { padding: 5px 3px; }.eligible-list .checkbox-label span { flex: 1; overflow: hidden; text-overflow: ellipsis; }.eligible-list small { color: var(--text-secondary); }.operation-run { margin-top: auto; width: 100%; }
@media (max-width: 760px) { .operation-layout { grid-template-columns: 1fr; }.target-panel { position: static; }.operation-grid { grid-template-columns: 1fr; } }
</style>
