<template>
  <div v-if="device">
    <div class="detail-header">
      <router-link to="/devices" class="back-link"><i class="fas fa-arrow-left" aria-hidden="true"></i>Devices</router-link>
      <div class="detail-title-row">
        <span class="device-icon" aria-hidden="true"><i :class="['fas', kind.icon]"></i></span>
        <div><h2>{{ device.name }}</h2><p>{{ identity }}</p></div>
        <StatusBadge :status="device.status" />
        <span :class="['badge', kind.badge]">{{ kind.label }}</span>
      </div>
      <div class="detail-actions">
        <button class="btn btn-primary btn-sm" :disabled="scanning" @click="scan"><i :class="['fas', scanning ? 'fa-spinner fa-spin' : 'fa-satellite-dish']" aria-hidden="true"></i>{{ scanning ? 'Scanning…' : 'Scan' }}</button>
        <router-link :to="`/operations?device=${device.id}`" class="btn btn-ghost btn-sm">Operations</router-link>
        <button v-if="device.transport === 'reachy_daemon'" class="btn btn-ghost btn-sm" @click="openSshSetup">{{ device.ssh_user ? 'Update app reset SSH' : 'Enable app reset' }}</button>
        <button class="btn btn-ghost btn-sm" @click="showEdit = true">Edit connection</button>
        <button class="btn btn-ghost btn-sm remove-action" @click="showRemove = true">Remove</button>
      </div>
    </div>

    <nav class="detail-tabs" aria-label="Device sections">
      <button v-for="tab in tabs" :key="tab" :class="{ active: activeTab === tab }" @click="activeTab = tab">{{ tab }}</button>
    </nav>

    <section v-if="activeTab === 'Summary'" class="detail-grid">
      <article class="card"><div class="card-body"><h3>Identity</h3><dl class="facts-list"><template v-for="item in identityFacts" :key="item.label"><dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></template></dl></div></article>
      <article class="card"><div class="card-body"><h3>Health</h3><dl class="facts-list"><dt>Status</dt><dd><StatusBadge :status="device.status" /></dd><dt>Last seen</dt><dd>{{ formatLongTime(device.last_seen) }}</dd><dt>Last discovery</dt><dd>{{ formatLongTime(device.discovered_at) }}</dd><template v-if="device.transport === 'ssh'"><dt>Reboot</dt><dd>{{ device.reboot_required ? 'Required' : 'Not required' }}</dd></template></dl></div></article>
      <article v-if="hardwareFacts.length" class="card full"><div class="card-body"><h3>Hardware</h3><div class="hardware-grid"><div v-for="item in hardwareFacts" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div></div></div></article>
    </section>

    <section v-else-if="activeTab === 'Hardware'" class="card"><div class="card-body"><h3>Discovered hardware</h3><div v-if="hardwareFacts.length" class="hardware-grid"><div v-for="item in hardwareFacts" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div></div><p v-else class="muted">No hardware-specific facts were reported. The device remains manageable through its portable capabilities.</p></div></section>

    <section v-else-if="activeTab === 'Software'" class="card"><div class="card-body"><h3>Software</h3><dl v-if="device.kind === 'robot'" class="facts-list"><template v-for="item in reachySoftwareFacts" :key="item.label"><dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></template></dl><dl v-else class="facts-list"><dt>Operating system</dt><dd>{{ device.os_version || 'Not reported' }}</dd><dt>OS family</dt><dd>{{ device.os_family || 'Not reported' }}</dd><dt v-if="device.driver_version">GPU driver</dt><dd v-if="device.driver_version">{{ device.driver_version }}</dd><dt v-if="device.cuda_version">CUDA</dt><dd v-if="device.cuda_version">{{ device.cuda_version }}</dd></dl></div></section>

    <section v-else-if="activeTab === 'Context'" class="context-grid">
      <article class="card"><div class="card-body"><div class="section-header"><div><h3>Manual attributes</h3><p>Add facts discovery can't determine. These are included in RAG after re-indexing.</p></div><button class="btn btn-ghost btn-sm" type="button" @click="addAnnotation"><i class="fas fa-plus" aria-hidden="true"></i>Add attribute</button></div><form class="annotations-form" @submit.prevent="saveAnnotations"><div v-for="(item, index) in annotationRows" :key="item.id" class="annotation-row"><input v-model="item.key" class="form-input" maxlength="80" placeholder="Motherboard model" aria-label="Attribute name" /><input v-model="item.value" class="form-input" maxlength="500" placeholder="ASRock Rack ROMED6U-2L2T" aria-label="Attribute value" /><button class="btn btn-ghost btn-icon remove-action" type="button" aria-label="Remove attribute" @click="annotationRows.splice(index, 1)"><i class="fas fa-trash" aria-hidden="true"></i></button></div><p v-if="!annotationRows.length" class="muted">No manual attributes yet.</p><button class="btn btn-primary btn-sm" type="submit" :disabled="savingAnnotations"><i :class="['fas', savingAnnotations ? 'fa-spinner fa-spin' : 'fa-save']" aria-hidden="true"></i>{{ savingAnnotations ? 'Saving…' : 'Save attributes' }}</button></form></div></article>
      <article class="card"><div class="card-body"><h3>Device documentation</h3><p class="muted">Upload manuals, notes, and other text for this device, then re-index context to make the relationship searchable.</p><router-link :to="`/context?device=${device.id}`" class="btn btn-primary btn-sm"><i class="fas fa-upload" aria-hidden="true"></i>Upload or manage documents</router-link></div></article>
    </section>

    <section v-else class="card"><div class="card-body"><div class="section-header"><div><h3>Available operations</h3><p>These actions are derived from discovered capabilities.</p></div><router-link :to="`/operations?device=${device.id}`" class="btn btn-primary btn-sm">Open Operations</router-link></div><div class="capability-grid"><span v-for="capability in device.capabilities" :key="capability"><i class="fas fa-check" aria-hidden="true"></i>{{ capability }}</span></div></div></section>

    <BaseModal :visible="showEdit" title="Edit device connection" @cancel="showEdit = false">
      <form id="edit-device-form" @submit.prevent="save">
        <div class="form-group"><label class="form-label" for="edit-name">Display name</label><input id="edit-name" v-model="edit.display_name" class="form-input" required /></div>
        <div class="form-group"><label class="form-label" for="edit-endpoint">Endpoint</label><input id="edit-endpoint" v-model="edit.endpoint" class="form-input" required /></div>
        <div v-if="device.transport === 'ssh'" class="form-group"><label class="form-label" for="edit-user">SSH user</label><input id="edit-user" v-model="edit.ssh_user" class="form-input" /></div>
      </form>
      <template #actions><button class="btn btn-ghost" @click="showEdit = false">Cancel</button><button class="btn btn-primary" type="submit" form="edit-device-form">Save</button></template>
    </BaseModal>
    <BaseModal :visible="showSshSetup" :title="device.ssh_user ? 'Update Reachy app reset SSH' : 'Enable Reachy app reset'" @cancel="closeSshSetup">
      <div class="callout callout-warn ssh-reset-warning">
        <i class="fas fa-triangle-exclamation callout-icon" aria-hidden="true"></i>
        <div class="callout-body"><div class="callout-title">This enables a destructive operation</div><div>Reset Reachy apps deletes <code>/venvs/apps_venv</code>. Installed apps must be reinstalled afterward.</div></div>
      </div>
      <form id="reachy-ssh-form" class="ssh-setup-grid" @submit.prevent="saveSshSetup">
        <div class="form-group"><label class="form-label" for="reachy-ssh-user">SSH user</label><input id="reachy-ssh-user" v-model.trim="sshSetup.ssh_user" class="form-input" required autocomplete="username" /></div>
        <label class="checkbox-label full-width"><input v-model="sshSetup.passwordless_ssh" type="checkbox" />Use the dedicated fleet SSH key</label>
        <div v-if="!sshSetup.passwordless_ssh" class="form-group"><label class="form-label" for="reachy-ssh-password">SSH password</label><input id="reachy-ssh-password" v-model="sshSetup.ssh_password" type="password" class="form-input" autocomplete="new-password" required /></div>
        <div v-else class="form-group"><label class="form-label" for="reachy-bootstrap-password">One-time bootstrap password <span class="optional">optional</span></label><input id="reachy-bootstrap-password" v-model="sshSetup.bootstrap_password" type="password" class="form-input" autocomplete="new-password" /></div>
        <div class="form-group"><label class="form-label" for="reachy-become-password">Sudo password <span class="optional">optional</span></label><input id="reachy-become-password" v-model="sshSetup.become_password" type="password" class="form-input" autocomplete="new-password" /></div>
      </form>
      <div v-if="sshPreviewing" class="callout callout-info"><i class="fas fa-spinner fa-spin callout-icon" aria-hidden="true"></i><div class="callout-body">Reading the Reachy SSH host key…</div></div>
      <div v-else-if="sshPreview" :class="['callout', sshPreview.reachable ? 'callout-success' : 'callout-danger']">
        <i :class="['fas', sshPreview.reachable ? 'fa-circle-check' : 'fa-circle-xmark', 'callout-icon']" aria-hidden="true"></i>
        <div class="callout-body"><div class="callout-title">{{ sshPreview.reachable ? 'SSH endpoint found' : 'SSH connection failed' }}</div><div>{{ sshPreview.detail }}</div></div>
      </div>
      <div v-if="sshPreview?.fingerprint" class="fingerprint-panel">
        <span>ED25519 fingerprint</span><code>{{ sshPreview.fingerprint }}</code>
        <label class="checkbox-label"><input v-model="sshFingerprintConfirmed" type="checkbox" />I verified this fingerprint through a trusted channel.</label>
      </div>
      <template #actions><button class="btn btn-ghost" type="button" @click="closeSshSetup">Cancel</button><button v-if="!sshPreview?.reachable" class="btn btn-primary" type="button" :disabled="sshPreviewing" @click="previewSshSetup">Retry SSH check</button><button v-else class="btn btn-primary" type="submit" form="reachy-ssh-form" :disabled="!canConfigureSsh || sshSaving">{{ sshSaving ? 'Verifying access…' : (device.ssh_user ? 'Update SSH access' : 'Enable app reset') }}</button></template>
    </BaseModal>
    <ConfirmDialog :visible="showRemove" title="Remove device" :message="`Remove ${device.name} from Fleet Manager? This deletes its saved connection and access associations but does not change the device itself.`" confirm-text="Remove device" danger-mode :require-text="device.inventory_name" @confirm="remove" @cancel="showRemove = false" />
  </div>
  <div v-else-if="loading" class="empty-state"><i class="fas fa-spinner fa-spin" aria-hidden="true"></i><p>Loading device…</p></div>
  <div v-else class="empty-state"><i class="fas fa-circle-exclamation" aria-hidden="true"></i><p>Device not found</p><router-link to="/devices" class="btn btn-primary btn-sm">Back to devices</router-link></div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { configureDeviceSsh, deleteDevice, getDevice, previewDeviceSsh, scanDevice, updateDevice, updateDeviceAnnotations } from "../api.js";
import StatusBadge from "../components/StatusBadge.vue";
import BaseModal from "../components/BaseModal.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import { deviceKind, devicePlatformName } from "../utils/devices.js";
import { formatLongTime } from "../utils/time.js";
const props = defineProps({ id: { type: String, required: true } });
const router = useRouter(); const device = ref(null); const loading = ref(true); const scanning = ref(false); const showEdit = ref(false); const showRemove = ref(false); const showSshSetup = ref(false); const sshPreviewing = ref(false); const sshSaving = ref(false); const sshPreview = ref(null); const sshFingerprintConfirmed = ref(false); const activeTab = ref("Summary"); const tabs = ["Summary", "Hardware", "Software", "Context", "Operations"]; const savingAnnotations = ref(false); const annotationRows = ref([]); let nextAnnotationId = 1;
const edit = reactive({ display_name: "", endpoint: "", ssh_user: "" });
const sshSetup = reactive({ ssh_user: "pollen", passwordless_ssh: true, ssh_password: "", bootstrap_password: "", become_password: "" });
const kind = computed(() => deviceKind(device.value?.kind));
const platformName = computed(() => devicePlatformName(device.value));
const identity = computed(() => [device.value?.vendor, device.value?.model, device.value?.endpoint].filter(Boolean).join(" · "));
const identityFacts = computed(() => [
  { label: "Inventory name", value: device.value.inventory_name }, { label: "Endpoint", value: device.value.endpoint }, { label: "Connection", value: device.value.transport === "ssh" ? "Linux over SSH" : "Reachy daemon" }, device.value.transport === "reachy_daemon" && { label: "SSH maintenance", value: device.value.ssh_user ? `Enabled as ${device.value.ssh_user}` : "Not configured" }, platformName.value && { label: "Platform", value: platformName.value }, device.value.architecture && { label: "Architecture", value: device.value.architecture },
].filter(Boolean));
const canConfigureSsh = computed(() => Boolean(sshPreview.value?.reachable && sshPreview.value?.fingerprint && sshFingerprintConfirmed.value && sshSetup.ssh_user && (sshSetup.passwordless_ssh || sshSetup.ssh_password)));
const hardwareFacts = computed(() => [
  device.value.facts?.motherboard?.model && { label: "Motherboard", value: [device.value.facts.motherboard.vendor, device.value.facts.motherboard.model, device.value.facts.motherboard.version].filter(Boolean).join(" ") }, device.value.facts?.bios?.version && { label: "BIOS", value: [device.value.facts.bios.vendor, device.value.facts.bios.version, device.value.facts.bios.date].filter(Boolean).join(" · ") }, device.value.facts?.cpu?.model && { label: "CPU", value: device.value.facts.cpu.model }, device.value.facts?.cpu?.vcpus && { label: "CPU topology", value: `${device.value.facts.cpu.sockets || 1} socket(s) · ${device.value.facts.cpu.vcpus} threads` }, device.value.memory_gb && { label: "Memory", value: `${device.value.memory_gb} GB` }, device.value.gpu_model && { label: "GPU", value: device.value.gpu_model }, device.value.nic_type && { label: "Network adapter", value: device.value.nic_type }, device.value.facts?.network?.primary_interface && { label: "Primary interface", value: device.value.facts.network.primary_interface }, device.value.nic_speed && { label: "Link speed", value: device.value.nic_speed }, device.value.disk_root_percent != null && { label: "Root storage used", value: `${device.value.disk_root_percent}%` }, device.value.facts?.storage_mounts?.length && { label: "Storage filesystems", value: String(device.value.facts.storage_mounts.length) }, device.value.facts?.robot_state?.control_mode && { label: "Motor control mode", value: device.value.facts.robot_state.control_mode },
].filter(Boolean));
const reachySoftwareFacts = computed(() => {
  const daemon = device.value.facts?.daemon || {}; const release = device.value.facts?.software?.update?.reachy_mini || {};
  return [
    { label: "Daemon state", value: daemon.state || "Running" },
    { label: "Robot name", value: daemon.robot_name || device.value.name },
    daemon.version && { label: "Installed version", value: daemon.version },
    release.current_version && { label: "Reachy Mini version", value: release.current_version },
    release.available_version && release.available_version !== "unknown" && { label: "Latest stable version", value: release.available_version },
    typeof release.is_available === "boolean" && { label: "Update", value: release.is_available ? "Available" : "Up to date" },
  ].filter(Boolean);
});
function resetAnnotationRows() { annotationRows.value = Object.entries(device.value?.annotations || {}).map(([key, value]) => ({ id: nextAnnotationId++, key, value })); }
function addAnnotation() { annotationRows.value.push({ id: nextAnnotationId++, key: "", value: "" }); }
async function load() { loading.value = true; try { device.value = await getDevice(props.id); Object.assign(edit, { display_name: device.value.name, endpoint: device.value.endpoint, ssh_user: device.value.ssh_user || "" }); resetAnnotationRows(); } catch (error) { device.value = null; } finally { loading.value = false; } }
async function scan() { scanning.value = true; try { const result = await scanDevice(props.id); window.$toast?.success(result.detail || "Scan started"); if (!result.job_id) await load(); } catch (error) { window.$toast?.error("Couldn't scan device", error); } finally { scanning.value = false; } }
async function save() { const payload = { display_name: edit.display_name, endpoint: edit.endpoint }; if (device.value.transport === "ssh") payload.ssh_user = edit.ssh_user; try { device.value = await updateDevice(props.id, payload); showEdit.value = false; window.$toast?.success("Device updated"); } catch (error) { window.$toast?.error("Couldn't update device", error); } }
async function saveAnnotations() { const annotations = {}; for (const item of annotationRows.value) { const key = item.key.trim(); const value = item.value.trim(); if (!key && !value) continue; if (!key || !value) { window.$toast?.error("Each manual attribute needs both a name and value"); return; } if (Object.hasOwn(annotations, key)) { window.$toast?.error(`Duplicate attribute: ${key}`); return; } annotations[key] = value; } savingAnnotations.value = true; try { device.value = await updateDeviceAnnotations(props.id, annotations); resetAnnotationRows(); window.$toast?.success("Manual attributes saved. Re-index context to publish them to search."); } catch (error) { window.$toast?.error("Couldn't save manual attributes", error); } finally { savingAnnotations.value = false; } }
async function openSshSetup() { Object.assign(sshSetup, { ssh_user: device.value.ssh_user || "pollen", passwordless_ssh: device.value.passwordless_ssh ?? true, ssh_password: "", bootstrap_password: "", become_password: "" }); sshPreview.value = null; sshFingerprintConfirmed.value = false; showSshSetup.value = true; await previewSshSetup(); }
function closeSshSetup() { showSshSetup.value = false; sshPreview.value = null; sshFingerprintConfirmed.value = false; }
async function previewSshSetup() { sshPreviewing.value = true; sshPreview.value = null; sshFingerprintConfirmed.value = false; try { sshPreview.value = await previewDeviceSsh(props.id); } catch (error) { window.$toast?.error("Couldn't inspect Reachy SSH", error); } finally { sshPreviewing.value = false; } }
async function saveSshSetup() { if (!canConfigureSsh.value) return; sshSaving.value = true; try { device.value = await configureDeviceSsh(props.id, { ...sshSetup, approval: { fingerprint: sshPreview.value.fingerprint } }); closeSshSetup(); window.$toast?.success("Reachy app reset is now available in Operations"); } catch (error) { window.$toast?.error("Couldn't enable Reachy app reset", error); } finally { sshSaving.value = false; } }
async function remove() { try { await deleteDevice(props.id); window.$toast?.success(`${device.value.name} removed`); showRemove.value = false; router.push("/devices"); } catch (error) { window.$toast?.error("Couldn't remove device", error); } }
onMounted(load);
</script>

<style scoped>
.detail-header { margin-bottom: 18px; }.back-link { display: inline-flex; gap: 6px; align-items: center; margin-bottom: 13px; font-size: 12px; }.detail-title-row { display: flex; align-items: center; gap: 12px; }.detail-title-row h2 { margin: 0; font-family: var(--font-mono); }.detail-title-row p { margin: 3px 0 0; color: var(--text-secondary); font-size: 12px; }.device-icon { width: 48px; height: 48px; border-radius: 12px; display: grid; place-items: center; background: var(--surface-info-soft); color: var(--color-accent); font-size: 20px; }.detail-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: -38px; }.remove-action { color: var(--color-danger); }.detail-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-subtle); margin-bottom: 18px; }.detail-tabs button { padding: 11px 15px; border: 0; border-bottom: 2px solid transparent; background: none; color: var(--text-secondary); cursor: pointer; }.detail-tabs button.active { border-bottom-color: var(--color-accent); color: var(--text-primary); font-weight: 650; }.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }.detail-grid .full { grid-column: 1/-1; }.facts-list { display: grid; grid-template-columns: minmax(120px, auto) 1fr; gap: 10px 18px; margin: 0; }.facts-list dt { color: var(--text-secondary); }.facts-list dd { margin: 0; text-align: right; }.hardware-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }.hardware-grid div { padding: 14px; background: var(--surface-light); border-radius: var(--radius-sm); display: flex; flex-direction: column; }.hardware-grid span { color: var(--text-secondary); font-size: 11px; }.hardware-grid strong { margin-top: 5px; }.section-header { display: flex; justify-content: space-between; align-items: center; }.section-header p { margin: 4px 0 0; color: var(--text-secondary); }.capability-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; margin-top: 16px; }.capability-grid span { padding: 10px; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: 11px; }.capability-grid i { margin-right: 8px; color: var(--color-success); }
.context-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr); gap: 16px; }.context-grid h3 { margin-top: 0; }.annotations-form { margin-top: 16px; }.annotation-row { display: grid; grid-template-columns: minmax(150px, .8fr) minmax(220px, 1.5fr) auto; gap: 8px; margin-bottom: 8px; }.annotations-form > .btn { margin-top: 8px; }.muted { color: var(--text-secondary); }
.ssh-reset-warning { margin-bottom: 16px; }.ssh-setup-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }.full-width { grid-column: 1/-1; margin: 4px 0 14px; }.optional { color: var(--text-muted); font-weight: 400; }.fingerprint-panel { margin-top: 12px; padding: 13px; background: var(--surface-light); border-radius: var(--radius-sm); }.fingerprint-panel > span { color: var(--text-secondary); font-size: 11px; text-transform: uppercase; letter-spacing: .4px; }.fingerprint-panel code { display: block; margin: 8px 0 14px; overflow-wrap: anywhere; }.fingerprint-panel .checkbox-label { align-items: flex-start; }
@media (max-width: 760px) { .detail-actions { margin-top: 14px; justify-content: flex-start; flex-wrap: wrap; }.detail-grid, .context-grid, .ssh-setup-grid { grid-template-columns: 1fr; }.detail-grid .full { grid-column: auto; }.detail-title-row { flex-wrap: wrap; }.annotation-row { grid-template-columns: 1fr auto; }.annotation-row input:nth-child(2) { grid-column: 1; } }
</style>
