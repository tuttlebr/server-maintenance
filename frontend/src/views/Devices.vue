<template>
  <div>
    <div class="page-header">
      <div><h2>Devices</h2><p class="page-subtitle">Compute, edge, and robotics inventory discovered by capability.</p></div>
      <div class="header-actions">
        <input ref="csvInput" class="visually-hidden" type="file" accept=".csv,text/csv" @change="loadCsv" />
        <button class="btn btn-ghost btn-sm" :disabled="!devices.length" title="Download all devices without stored passwords" @click="downloadCsv"><i class="fas fa-download" aria-hidden="true"></i>Download CSV</button>
        <button class="btn btn-ghost btn-sm" @click="csvInput?.click()"><i class="fas fa-file-csv" aria-hidden="true"></i>Import CSV</button>
        <button class="btn btn-primary btn-sm" @click="openAdd"><i class="fas fa-plus" aria-hidden="true"></i>Add device</button>
      </div>
    </div>

    <div class="filter-bar" role="search" aria-label="Filter devices">
      <div class="search-field"><i class="fas fa-search" aria-hidden="true"></i><input v-model="search" class="form-input" placeholder="Search name, vendor, model, platform, or endpoint" /></div>
      <select v-model="kindFilter" class="form-select" aria-label="Filter by device type"><option value="">All types</option><option v-for="item in availableKinds" :key="item" :value="item">{{ deviceKind(item).label }}</option></select>
      <select v-model="capabilityFilter" class="form-select" aria-label="Filter by capability"><option value="">All capabilities</option><option v-for="item in availableCapabilities" :key="item" :value="item">{{ capabilityLabel(item) }}</option></select>
      <select v-model="statusFilter" class="form-select" aria-label="Filter by status"><option value="">All states</option><option value="online">Online</option><option value="offline">Offline</option><option value="unknown">Unknown</option><option value="attention">Needs attention</option></select>
    </div>

    <div class="results-summary">{{ filteredDevices.length }} of {{ devices.length }} devices</div>
    <div v-if="filteredDevices.length" class="device-grid"><DeviceCard v-for="device in filteredDevices" :key="device.id" :device="device" /></div>
    <div v-else-if="store.hasLoadedOnce" class="empty-state">
      <i class="fas fa-server" aria-hidden="true"></i>
      <p>{{ devices.length ? 'No devices match these filters' : 'No devices have been added yet' }}</p>
      <button v-if="!devices.length" class="btn btn-primary btn-sm" @click="openAdd">Add your first device</button>
    </div>

    <BaseModal :visible="showAdd" :title="stepTitle" size="lg" @cancel="closeAdd">
      <ol class="stepper" aria-label="Add device progress">
        <li v-for="(label, index) in steps" :key="label" :class="{ active: step === index + 1, done: step > index + 1 }"><span>{{ index + 1 }}</span>{{ label }}</li>
      </ol>

      <form v-if="step === 1" id="device-connect-form" @submit.prevent="step = 2">
        <fieldset class="transport-options">
          <legend>How should Fleet Manager connect?</legend>
          <label :class="['transport-card', { selected: draft.transport === 'ssh' }]">
            <input v-model="draft.transport" type="radio" value="ssh" />
            <i class="fas fa-terminal" aria-hidden="true"></i><span><strong>Linux over SSH</strong><small>Servers, workstations, and edge devices</small></span>
          </label>
          <label :class="['transport-card', { selected: draft.transport === 'reachy_daemon' }]">
            <input v-model="draft.transport" type="radio" value="reachy_daemon" />
            <i class="fas fa-robot" aria-hidden="true"></i><span><strong>Reachy Mini Wireless</strong><small>Read-only daemon health and state</small></span>
          </label>
        </fieldset>
      </form>

      <form v-else-if="step === 2" id="device-details-form" class="form-grid" @submit.prevent="discover">
        <div class="form-group"><label class="form-label" for="device-name">Device name</label><input id="device-name" v-model.trim="draft.name" class="form-input" required placeholder="lab-node-01" /></div>
        <div class="form-group"><label class="form-label" for="device-endpoint">Network endpoint</label><input id="device-endpoint" v-model.trim="draft.endpoint" class="form-input" required placeholder="192.0.2.10 or device.local" /></div>
        <template v-if="draft.transport === 'ssh'">
          <div class="form-group"><label class="form-label" for="ssh-user">SSH user</label><input id="ssh-user" v-model.trim="draft.ssh_user" class="form-input" required placeholder="fleetadmin" /></div>
          <label class="checkbox-label full-width"><input v-model="draft.passwordless_ssh" type="checkbox" />Use the dedicated fleet SSH key</label>
          <div v-if="!draft.passwordless_ssh" class="form-group"><label class="form-label" for="ssh-password">SSH password</label><input id="ssh-password" v-model="draft.ssh_password" type="password" class="form-input" autocomplete="new-password" required /></div>
          <div v-else class="form-group"><label class="form-label" for="bootstrap-password">One-time bootstrap password <span class="optional">optional</span></label><input id="bootstrap-password" v-model="draft.bootstrap_password" type="password" class="form-input" autocomplete="new-password" /></div>
          <div class="form-group"><label class="form-label" for="become-password">Sudo password <span class="optional">optional</span></label><input id="become-password" v-model="draft.become_password" type="password" class="form-input" autocomplete="new-password" /></div>
        </template>
        <div v-else class="form-group"><label class="form-label" for="daemon-port">Daemon port</label><input id="daemon-port" v-model.number="draft.daemon_port" type="number" min="1" max="65535" class="form-input" /></div>
      </form>

      <div v-else-if="step === 3">
        <div :class="['callout', discovery.reachable ? 'callout-success' : 'callout-danger']">
          <i :class="['fas', discovery.reachable ? 'fa-circle-check' : 'fa-circle-xmark', 'callout-icon']" aria-hidden="true"></i>
          <div class="callout-body"><div class="callout-title">{{ discovery.reachable ? 'Connection verified' : 'Connection failed' }}</div><div>{{ discovery.detail }}</div></div>
        </div>
        <div v-if="discovery.reachable" class="review-grid">
          <div><span>Detected type</span><strong>{{ deviceKind(discovery.kind).label }}</strong></div>
          <div v-if="discovery.vendor"><span>Vendor</span><strong>{{ discovery.vendor }}</strong></div>
          <div v-if="discovery.model"><span>Model</span><strong>{{ discovery.model }}</strong></div>
          <div><span>Capabilities</span><strong>{{ discovery.capabilities.length }}</strong></div>
        </div>
        <div v-if="discovery.fingerprint" class="fingerprint-panel">
          <span>ED25519 fingerprint</span><code>{{ discovery.fingerprint }}</code>
          <label class="checkbox-label"><input v-model="fingerprintConfirmed" type="checkbox" />I verified this fingerprint through a trusted channel.</label>
        </div>
        <div v-if="discovery.reachable && !discovery.fingerprint" class="callout callout-info"><div class="callout-body">Reachy discovery is read-only and never exposes motion, motors, camera, audio, or app controls. Its daemon connection is not identity-verified, so use it only on a trusted management network.</div></div>
      </div>

      <template #actions>
        <button type="button" class="btn btn-ghost" @click="step === 1 ? closeAdd() : step--">{{ step === 1 ? 'Cancel' : 'Back' }}</button>
        <button v-if="step === 1" type="submit" form="device-connect-form" class="btn btn-primary">Continue</button>
        <button v-else-if="step === 2" type="submit" form="device-details-form" class="btn btn-primary" :disabled="working">{{ working ? 'Connecting…' : 'Discover device' }}</button>
        <button v-else type="button" class="btn btn-primary" :disabled="!canAdd || working" @click="enroll">{{ working ? 'Adding…' : 'Add device' }}</button>
      </template>
    </BaseModal>

    <BaseModal :visible="showBulk" title="Import devices from CSV" size="lg" @cancel="closeBulk">
      <div class="callout callout-info bulk-guidance">
        <div class="callout-body">Discovery runs before enrollment. Passwords are never shown in this review. Verify every SSH fingerprint through a trusted channel.</div>
      </div>
      <div class="bulk-summary">
        <strong>{{ bulkRows.length }} device{{ bulkRows.length === 1 ? '' : 's' }}</strong>
        <span v-if="bulkPhase === 'discovering'">Discovering {{ bulkProgress }} of {{ bulkRows.length }}…</span>
        <span v-else-if="bulkPhase === 'adding'">Adding {{ bulkProgress }} of {{ bulkTargetCount }}…</span>
        <span v-else>{{ bulkStatusSummary }}</span>
      </div>
      <div class="bulk-table-wrap">
        <table class="bulk-table">
          <thead><tr><th>Device</th><th>Connection</th><th>Status</th><th>SSH fingerprint</th></tr></thead>
          <tbody>
            <tr v-for="row in bulkRows" :key="row.key">
              <td><strong>{{ row.device.name || 'Unnamed row' }}</strong><small>{{ row.device.endpoint || 'No endpoint' }}</small></td>
              <td>{{ row.device.transport === 'reachy_daemon' ? 'Reachy daemon' : 'SSH' }}</td>
              <td><span :class="['bulk-state', `state-${row.state}`]">{{ bulkStateLabel(row) }}</span><small v-if="row.error" class="bulk-error">{{ row.error }}</small></td>
              <td><code v-if="row.discovery?.fingerprint">{{ row.discovery.fingerprint }}</code><span v-else>Not required</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <label v-if="fingerprintedBulkRows.length" class="checkbox-label bulk-approval">
        <input v-model="bulkFingerprintsConfirmed" type="checkbox" />
        I verified every listed SSH fingerprint through a trusted channel.
      </label>
      <div v-if="bulkPhase === 'done'" class="callout callout-success"><div class="callout-body">Import finished. {{ addedBulkCount }} device{{ addedBulkCount === 1 ? '' : 's' }} added.</div></div>
      <template #actions>
        <button type="button" class="btn btn-ghost" :disabled="bulkBusy" @click="closeBulk">{{ bulkPhase === 'done' ? 'Close' : 'Cancel' }}</button>
        <button v-if="bulkPhase === 'review'" type="button" class="btn btn-primary" :disabled="!bulkRows.length" @click="discoverBulk">Discover {{ bulkRows.length }}</button>
        <button v-else-if="bulkPhase === 'discovered'" type="button" class="btn btn-primary" :disabled="!canAddBulk" @click="enrollBulk">Add {{ readyBulkRows.length }} ready</button>
      </template>
    </BaseModal>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import Papa from "papaparse";
import { useRoute, useRouter } from "vue-router";
import { addDevice, discoverDevice } from "../api.js";
import { useDevicesStore } from "../stores/devices.js";
import DeviceCard from "../components/DeviceCard.vue";
import BaseModal from "../components/BaseModal.vue";
import { createDeviceCsv } from "../utils/deviceCsv.js";
import { deviceKind, deviceMatchesSearch } from "../utils/devices.js";

const route = useRoute(); const router = useRouter(); const store = useDevicesStore();
const devices = computed(() => store.devices); const showAdd = ref(false); const step = ref(1); const working = ref(false); const discovery = ref({ capabilities: [] }); const fingerprintConfirmed = ref(false);
const csvInput = ref(null); const showBulk = ref(false); const bulkRows = ref([]); const bulkPhase = ref("review"); const bulkProgress = ref(0); const bulkTargetCount = ref(0); const bulkFingerprintsConfirmed = ref(false);
const search = ref(""); const kindFilter = ref(String(route.query.kind || "")); const capabilityFilter = ref(String(route.query.capability || "")); const statusFilter = ref(route.query.attention ? "attention" : "");
const steps = ["Connection", "Details", "Review"];
const stepTitle = computed(() => `${steps[step.value - 1]} · Add device`);
const emptyDraft = () => ({ name: "", endpoint: "", transport: "ssh", ssh_user: "", ssh_password: "", become_password: "", bootstrap_password: "", passwordless_ssh: true, daemon_port: 8000 });
const draft = reactive(emptyDraft());
const availableKinds = computed(() => [...new Set(devices.value.map((device) => device.kind))].sort());
const availableCapabilities = computed(() => [...new Set(devices.value.flatMap((device) => device.capabilities || []))].sort());
const filteredDevices = computed(() => devices.value.filter((device) => {
  const attention = device.status !== "online" || device.reboot_required || (device.disk_root_percent || 0) >= 85;
  return deviceMatchesSearch(device, search.value) && (!kindFilter.value || device.kind === kindFilter.value) && (!capabilityFilter.value || device.capabilities.includes(capabilityFilter.value)) && (!statusFilter.value || (statusFilter.value === "attention" ? attention : device.status === statusFilter.value));
}));
const canAdd = computed(() => discovery.value.reachable && (!discovery.value.fingerprint || fingerprintConfirmed.value));
const bulkBusy = computed(() => ["discovering", "adding"].includes(bulkPhase.value));
const readyBulkRows = computed(() => bulkRows.value.filter((row) => row.state === "ready"));
const fingerprintedBulkRows = computed(() => readyBulkRows.value.filter((row) => row.discovery?.fingerprint));
const addedBulkCount = computed(() => bulkRows.value.filter((row) => row.state === "added").length);
const canAddBulk = computed(() => readyBulkRows.value.length > 0 && (!fingerprintedBulkRows.value.length || bulkFingerprintsConfirmed.value));
const bulkStatusSummary = computed(() => {
  const ready = readyBulkRows.value.length; const failed = bulkRows.value.filter((row) => row.state === "failed").length;
  if (bulkPhase.value === "review") return "Review parsed rows before discovery";
  if (bulkPhase.value === "done") return `${addedBulkCount.value} added${failed ? `, ${failed} failed` : ""}`;
  return `${ready} ready${failed ? `, ${failed} need attention` : ""}`;
});
function capabilityLabel(value) { return value.split(".").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" · "); }
function downloadCsv() {
  if (!devices.value.length) return;
  const content = createDeviceCsv(devices.value);
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  const now = new Date();
  const date = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"), String(now.getDate()).padStart(2, "0")].join("-");
  link.href = url; link.download = `fleet-manager-devices-${date}.csv`; document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
  window.$toast?.info(`Downloaded ${devices.value.length} device${devices.value.length === 1 ? "" : "s"}. Stored passwords aren't included.`);
}
function openAdd() { showAdd.value = true; }
function closeAdd() { showAdd.value = false; step.value = 1; discovery.value = { capabilities: [] }; fingerprintConfirmed.value = false; Object.assign(draft, emptyDraft()); if (route.query.add) router.replace({ path: "/devices", query: {} }); }
async function discover() { working.value = true; try { discovery.value = await discoverDevice({ ...draft }); step.value = 3; } catch (error) { window.$toast?.error("Couldn't discover device", error); } finally { working.value = false; } }
async function enroll() { working.value = true; try { const result = await addDevice({ device: { ...draft }, approval: discovery.value.fingerprint ? { fingerprint: discovery.value.fingerprint } : null }); window.$toast?.success(`${result.name} added`); await store.refresh({ force: true }); closeAdd(); router.push(`/devices/${result.id}`); } catch (error) { window.$toast?.error("Couldn't add device", error); } finally { working.value = false; } }
function parseCsvBoolean(value, defaultValue = true) { const normalized = String(value ?? "").trim().toLowerCase(); if (!normalized) return defaultValue; return ["true", "yes", "1", "key", "passwordless"].includes(normalized); }
function normalizeCsvRow(row, index) {
  const transport = String(row.transport || "ssh").trim().toLowerCase();
  const port = Number.parseInt(String(row.daemon_port || "8000"), 10);
  return {
    key: `${index}-${row.name || "row"}`,
    device: {
      name: String(row.name || "").trim(), endpoint: String(row.endpoint || "").trim(),
      transport, ssh_user: String(row.ssh_user || "").trim() || null,
      ssh_password: String(row.ssh_password || "") || null, become_password: String(row.become_password || "") || null,
      bootstrap_password: String(row.bootstrap_password || "") || null,
      passwordless_ssh: parseCsvBoolean(row.passwordless_ssh, true), daemon_port: Number.isFinite(port) ? port : 8000,
    },
    state: "pending", discovery: null, error: "",
  };
}
function loadCsv(event) {
  const file = event.target.files?.[0]; if (!file) return;
  Papa.parse(file, {
    header: true, skipEmptyLines: "greedy", transformHeader: (header) => header.trim().toLowerCase(),
    complete: ({ data, errors, meta }) => {
      const required = ["name", "endpoint", "transport"]; const missing = required.filter((field) => !meta.fields?.includes(field));
      if (missing.length || errors.length) { window.$toast?.error("Couldn't read device CSV", missing.length ? `Missing columns: ${missing.join(", ")}` : errors[0].message); event.target.value = ""; return; }
      bulkRows.value = data.map(normalizeCsvRow); bulkPhase.value = "review"; bulkProgress.value = 0; bulkFingerprintsConfirmed.value = false; showBulk.value = true; event.target.value = "";
    },
    error: (error) => { window.$toast?.error("Couldn't read device CSV", error); event.target.value = ""; },
  });
}
async function discoverBulk() {
  bulkPhase.value = "discovering"; bulkProgress.value = 0;
  for (const row of bulkRows.value) {
    row.state = "discovering"; row.error = "";
    try { row.discovery = await discoverDevice(row.device); row.state = row.discovery.reachable ? "ready" : "failed"; if (!row.discovery.reachable) row.error = row.discovery.detail; }
    catch (error) { row.state = "failed"; row.error = error.message || "Discovery failed"; }
    bulkProgress.value++;
  }
  bulkPhase.value = "discovered";
}
async function enrollBulk() {
  const ready = [...readyBulkRows.value]; bulkPhase.value = "adding"; bulkProgress.value = 0; bulkTargetCount.value = ready.length;
  for (const row of ready) {
    row.state = "adding";
    try { await addDevice({ device: row.device, approval: row.discovery?.fingerprint ? { fingerprint: row.discovery.fingerprint } : null }); row.state = "added"; }
    catch (error) { row.state = "failed"; row.error = error.message || "Enrollment failed"; }
    bulkProgress.value++;
  }
  await store.refresh({ force: true }); bulkPhase.value = "done";
}
function closeBulk() { if (bulkBusy.value) return; showBulk.value = false; bulkRows.value = []; bulkPhase.value = "review"; bulkProgress.value = 0; bulkTargetCount.value = 0; bulkFingerprintsConfirmed.value = false; }
function bulkStateLabel(row) { return ({ pending: "Pending", discovering: "Discovering…", ready: "Ready", adding: "Adding…", added: "Added", failed: "Needs attention" })[row.state] || row.state; }
watch(() => route.query.add, (value) => { if (value) openAdd(); }, { immediate: true });
onMounted(() => store.start()); onUnmounted(() => store.stop());
</script>

<style scoped>
.page-subtitle { margin: 4px 0 0; color: var(--text-secondary); }.header-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }.filter-bar { display: grid; grid-template-columns: minmax(260px, 1fr) repeat(3, minmax(145px, auto)); gap: 10px; padding: 12px; background: var(--surface-white); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }.search-field { position: relative; }.search-field i { position: absolute; left: 12px; top: 12px; color: var(--text-muted); }.search-field input { padding-left: 34px; }.results-summary { margin: 14px 0 9px; color: var(--text-secondary); font-size: 12px; }.device-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.stepper { display: grid; grid-template-columns: repeat(3, 1fr); list-style: none; padding: 0; margin: 0 0 24px; counter-reset: none; }.stepper li { position: relative; display: flex; align-items: center; gap: 8px; color: var(--text-muted); font-size: 12px; }.stepper li::after { content: ""; height: 1px; flex: 1; background: var(--border-subtle); }.stepper li:last-child::after { display: none; }.stepper li span { width: 25px; height: 25px; border: 1px solid var(--border-color); border-radius: 50%; display: grid; place-items: center; }.stepper li.active { color: var(--text-primary); font-weight: 700; }.stepper li.active span, .stepper li.done span { background: var(--color-accent); color: #fff; border-color: var(--color-accent); }
.transport-options { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; border: 0; padding: 0; }.transport-options legend { grid-column: 1/-1; margin-bottom: 10px; font-weight: 650; }.transport-card { display: flex; align-items: center; gap: 14px; padding: 18px; border: 2px solid var(--border-subtle); border-radius: var(--radius-md); cursor: pointer; }.transport-card.selected { border-color: var(--color-accent); background: var(--surface-info-soft); }.transport-card > i { font-size: 24px; color: var(--color-accent); }.transport-card span { display: flex; flex-direction: column; }.transport-card small { margin-top: 3px; color: var(--text-secondary); }.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }.full-width { grid-column: 1/-1; margin: 4px 0 14px; }.optional { color: var(--text-muted); font-weight: 400; }.review-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 16px 0; }.review-grid div, .fingerprint-panel { padding: 13px; background: var(--surface-light); border-radius: var(--radius-sm); }.review-grid div { display: flex; flex-direction: column; }.review-grid span, .fingerprint-panel > span { color: var(--text-secondary); font-size: 11px; text-transform: uppercase; letter-spacing: .4px; }.fingerprint-panel code { display: block; margin: 8px 0 14px; overflow-wrap: anywhere; }.fingerprint-panel .checkbox-label { align-items: flex-start; }
.bulk-guidance { margin-bottom: 12px; }.bulk-summary { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 10px; color: var(--text-secondary); }.bulk-summary strong { color: var(--text-primary); }.bulk-table-wrap { max-height: 390px; overflow: auto; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }.bulk-table { width: 100%; border-collapse: collapse; font-size: 12px; }.bulk-table th, .bulk-table td { padding: 10px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--border-subtle); }.bulk-table th { position: sticky; top: 0; background: var(--surface-light); color: var(--text-secondary); z-index: 1; }.bulk-table td strong, .bulk-table td small { display: block; }.bulk-table td small { margin-top: 3px; color: var(--text-secondary); }.bulk-table code { display: block; max-width: 260px; overflow-wrap: anywhere; }.bulk-state { font-weight: 650; }.state-ready, .state-added { color: var(--color-success); }.state-failed, .bulk-error { color: var(--color-danger) !important; }.bulk-approval { align-items: flex-start; margin-top: 14px; }
@media (max-width: 850px) { .filter-bar { grid-template-columns: 1fr 1fr; }.search-field { grid-column: 1/-1; } }
@media (max-width: 620px) { .filter-bar, .transport-options, .form-grid, .review-grid { grid-template-columns: 1fr; } }
</style>
