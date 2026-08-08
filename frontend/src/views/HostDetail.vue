<template>
  <div v-if="host">
    <div class="page-header">
      <div class="flex items-center gap-sm">
        <button class="btn btn-ghost btn-sm" aria-label="Back to dashboard" @click="$router.push('/')">
          <i class="fas fa-arrow-left" aria-hidden="true"></i>
        </button>
        <h2>{{ host.hostname }}</h2>
        <StatusBadge :status="host.status || 'unknown'" with-tooltip />
        <span :class="['badge', getMachineType(host.machine_type).badge]">
          {{ getMachineType(host.machine_type).label }}
        </span>
      </div>
      <div class="flex gap-xs">
        <button class="btn btn-ghost btn-sm" @click="openEditModal">
          <i class="fas fa-pen" aria-hidden="true"></i> Edit
        </button>
        <button class="btn btn-ghost btn-sm" :disabled="scanning" @click="scan">
          <i :class="['fas', scanning ? 'fa-spinner fa-spin' : 'fa-satellite-dish']" aria-hidden="true"></i>
          {{ scanning ? 'Scanning…' : 'Scan' }}
        </button>
        <button
          v-if="getMachineType(host.machine_type).hasGpu"
          class="btn btn-primary btn-sm"
          @click="confirmDrv = true"
        >
          <i class="fas fa-download" aria-hidden="true"></i> Upgrade Drivers
        </button>
        <button class="btn btn-danger btn-sm" :aria-label="`Delete host ${host.hostname}`" @click="confirmDelete = true">
          <i class="fas fa-trash" aria-hidden="true"></i>
        </button>
      </div>
    </div>

    <!-- Info Panels -->
    <div class="grid" style="margin-bottom: var(--space-md)">
      <div v-if="getMachineType(host.machine_type).hasGpu" class="col-4 col-md-6 col-sm-12">
        <div class="card">
          <div class="card-body">
            <h5 style="margin-bottom: 12px; color: var(--text-secondary)">GPU</h5>
            <div class="info-row"><span>Model</span><span>{{ host.gpu_model || '--' }}</span></div>
            <div class="info-row"><span>Driver</span><span>{{ host.driver_version || '--' }}</span></div>
            <div class="info-row"><span>CUDA</span><span>{{ host.cuda_version || '--' }}</span></div>
            <div class="info-row"><span>Memory</span><span>{{ host.memory_gb ? host.memory_gb + ' GB' : '--' }}</span></div>
          </div>
        </div>
      </div>
      <div v-else class="col-4 col-md-6 col-sm-12">
        <div class="card">
          <div class="card-body">
            <h5 style="margin-bottom: 12px; color: var(--text-secondary)">System</h5>
            <div class="info-row"><span>Memory</span><span>{{ host.memory_gb ? host.memory_gb + ' GB' : '--' }}</span></div>
          </div>
        </div>
      </div>
      <div class="col-4 col-md-6 col-sm-12">
        <div class="card">
          <div class="card-body">
            <h5 style="margin-bottom: 12px; color: var(--text-secondary)">Storage</h5>
            <div class="disk-row">
              <span>Root (/)</span>
              <div class="progress-bar" style="flex: 1; margin: 0 12px">
                <div class="progress-fill" :class="diskClass(host.disk_root_percent)" :style="{ width: (host.disk_root_percent || 0) + '%' }"></div>
              </div>
              <span>{{ host.disk_root_percent || 0 }}%</span>
            </div>
            <div class="disk-row" style="margin-top: 12px">
              <span>Other max</span>
              <div class="progress-bar" style="flex: 1; margin: 0 12px">
                <div class="progress-fill" :class="diskClass(host.disk_raid_percent)" :style="{ width: (host.disk_raid_percent || 0) + '%' }"></div>
              </div>
              <span>{{ host.disk_raid_percent || 0 }}%</span>
            </div>
            <div v-if="host.reboot_required" style="margin-top: 12px; color: var(--color-danger); font-size: 13px; font-weight: 500">
              <i class="fas fa-exclamation-triangle" aria-hidden="true"></i> Reboot required
              <InfoTooltip :text="GLOSSARY.rebootRequired" />
            </div>
          </div>
        </div>
      </div>
      <div class="col-4 col-md-12 col-sm-12">
        <div class="card">
          <div class="card-body">
            <h5 style="margin-bottom: 12px; color: var(--text-secondary)">Network</h5>
            <div class="info-row"><span>NIC</span><span>{{ host.nic_type || '--' }}</span></div>
            <div class="info-row"><span>Speed</span><span>{{ host.nic_speed || '--' }}</span></div>
            <div v-if="getMachineType(host.machine_type).hasFabricManager" class="info-row"><span>Fabric Mgr <InfoTooltip :text="GLOSSARY.fabricManager" /></span><span>{{ host.fabric_manager_status || '--' }}</span></div>
            <div v-if="host.cuda_version" class="info-row"><span>CUDA <InfoTooltip :text="GLOSSARY.cuda" /></span><span>{{ host.cuda_version }}</span></div>
            <div class="info-row"><span>OS</span><span>{{ host.os_version || '--' }}</span></div>
            <div class="info-row"><span>IP</span><span>{{ host.ip_address || '--' }}</span></div>
            <div class="info-row"><span>SSH User</span><span>{{ host.ansible_user || '--' }}</span></div>
            <div class="info-row"><span>SSH Auth</span><span>{{ host.passwordless_ssh ? 'Key' : 'Password' }}</span></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit Host Modal -->
    <BaseModal :visible="showEdit" :title="`Edit ${host.hostname}`" size="md" @cancel="showEdit = false">
      <form id="edit-host-form" @submit.prevent="handleEdit">
        <div class="form-group">
          <label class="form-label" :for="`edit-ip-${host.hostname}`">IP Address</label>
          <input
            :id="`edit-ip-${host.hostname}`"
            v-model="editForm.ip_address"
            class="form-input"
            placeholder="10.0.0.2"
          />
        </div>
        <div class="form-group">
          <label class="form-label" :for="`edit-type-${host.hostname}`">Machine Type</label>
          <select :id="`edit-type-${host.hostname}`" v-model="editForm.machine_type" class="form-select">
            <option v-for="(mt, key) in MACHINE_TYPES" :key="key" :value="key">{{ mt.label }}</option>
          </select>
        </div>
        <div class="separator"></div>
        <h4 style="margin-bottom: var(--space-xs); font-size: 13px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px">
          SSH Credentials
        </h4>
        <div class="form-group">
          <label class="form-label" :for="`edit-user-${host.hostname}`">SSH Username</label>
          <input :id="`edit-user-${host.hostname}`" v-model="editForm.ansible_user" class="form-input" placeholder="btuttle" />
        </div>
        <label class="checkbox-label auth-toggle">
          <input type="checkbox" v-model="editForm.passwordless_ssh" @change="onPasswordlessToggle" />
          Passwordless SSH
        </label>
        <div class="form-group">
          <label class="form-label" :for="`edit-pw-${host.hostname}`">SSH Password</label>
          <input
            :id="`edit-pw-${host.hostname}`"
            v-model="editForm.ansible_password"
            type="password"
            class="form-input"
            :disabled="editForm.passwordless_ssh"
            :placeholder="editForm.passwordless_ssh ? 'Key-based auth enabled' : 'Leave blank to keep current'"
          />
        </div>
        <div class="form-group">
          <label class="form-label" :for="`edit-sudo-${host.hostname}`">Sudo Password (optional)</label>
          <input
            :id="`edit-sudo-${host.hostname}`"
            v-model="editForm.ansible_become_password"
            type="password"
            class="form-input"
            :placeholder="editForm.passwordless_ssh ? 'Leave blank for passwordless sudo' : 'Leave blank to keep current'"
          />
        </div>
      </form>
      <template #actions>
        <button type="button" class="btn btn-ghost" data-cancel @click="showEdit = false">Cancel</button>
        <button type="submit" form="edit-host-form" class="btn btn-green">Save Changes</button>
      </template>
    </BaseModal>

    <ConfirmDialog
      :visible="confirmDelete"
      title="Remove host from fleet"
      :message="`This permanently removes ${host.hostname} from the fleet database. SSH credentials and scan history will be lost. The remote machine itself is untouched.`"
      confirm-text="Delete host"
      :danger-mode="true"
      danger-label="Destructive — type to confirm"
      :require-text="host.hostname"
      @confirm="handleDelete"
      @cancel="confirmDelete = false"
    />

    <ConfirmDialog
      :visible="confirmDrv"
      title="Upgrade GPU drivers"
      :message="`This runs the driver upgrade playbook on ${host.hostname}. The host may reboot or hang briefly. Existing GPU workloads will be interrupted.`"
      confirm-text="Start upgrade"
      :danger-mode="true"
      @confirm="upgradeDrv"
      @cancel="confirmDrv = false"
    />
  </div>
  <div v-else class="empty-state">
    <i class="fas fa-spinner fa-spin" aria-hidden="true"></i>
    <p>Loading host details…</p>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { useIntervalFn, useDocumentVisibility } from "@vueuse/core";
import { getHost, scanHost, deleteHost, upgradeDrivers, updateHost, getJob } from "../api.js";
import StatusBadge from "../components/StatusBadge.vue";
import InfoTooltip from "../components/InfoTooltip.vue";
import { GLOSSARY } from "../glossary.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import BaseModal from "../components/BaseModal.vue";
import { getMachineType, MACHINE_TYPES } from "../machineTypes.js";

const props = defineProps({ hostname: String });
const router = useRouter();
const host = ref(null);
const confirmDelete = ref(false);
const confirmDrv = ref(false);
const showEdit = ref(false);
const editForm = ref({});
const scanning = ref(false);
const visibility = useDocumentVisibility();

let pollHandle = null;

function openEditModal() {
  editForm.value = {
    ip_address: host.value.ip_address || "",
    machine_type: host.value.machine_type || "unknown",
    ansible_user: host.value.ansible_user || "",
    ansible_password: "",
    ansible_become_password: "",
    passwordless_ssh: !!host.value.passwordless_ssh,
  };
  showEdit.value = true;
}

function onPasswordlessToggle() {
  if (editForm.value.passwordless_ssh) editForm.value.ansible_password = "";
}

async function handleEdit() {
  try {
    if (!editForm.value.passwordless_ssh && host.value.passwordless_ssh && !editForm.value.ansible_password) {
      window.$toast?.error("Enter an SSH password or keep passwordless SSH enabled");
      return;
    }

    const payload = {};
    if (editForm.value.ip_address) payload.ip_address = editForm.value.ip_address;
    if (editForm.value.machine_type) payload.machine_type = editForm.value.machine_type;
    if (editForm.value.ansible_user) payload.ansible_user = editForm.value.ansible_user;
    payload.passwordless_ssh = !!editForm.value.passwordless_ssh;
    if (editForm.value.passwordless_ssh) payload.ansible_password = "";
    else if (editForm.value.ansible_password) payload.ansible_password = editForm.value.ansible_password;
    if (editForm.value.ansible_become_password) payload.ansible_become_password = editForm.value.ansible_become_password;

    await updateHost(props.hostname, payload);
    showEdit.value = false;
    window.$toast?.success(`Saved changes to ${props.hostname}`);
    load();
  } catch (e) {
    window.$toast?.error(`Couldn't update ${props.hostname}`, e);
  }
}

async function load() {
  try {
    host.value = await getHost(props.hostname);
  } catch (e) {
    window.$toast?.error(`Couldn't load ${props.hostname}`, e);
  }
}

async function scan() {
  if (scanning.value) return;
  try {
    scanning.value = true;
    const result = await scanHost(props.hostname);
    window.$toast?.success(`Scan started on ${props.hostname}`);
    if (result?.job_id) {
      pollForCompletion(result.job_id);
    } else {
      scanning.value = false;
    }
  } catch (e) {
    scanning.value = false;
    window.$toast?.error(`Couldn't start scan on ${props.hostname}`, e);
  }
}

function pollForCompletion(jobId) {
  // Track the job state and finalize when done. useIntervalFn auto-cleans on
  // unmount and we pause when the tab is hidden to avoid wasted polling.
  if (pollHandle) {
    pollHandle.pause();
    pollHandle = null;
  }
  pollHandle = useIntervalFn(
    async () => {
      if (visibility.value !== "visible") return;
      try {
        const job = await getJob(jobId);
        if (job.status === "success" || job.status === "failed") {
          pollHandle.pause();
          pollHandle = null;
          scanning.value = false;
          if (job.status === "success") {
            window.$toast?.success(`Scan complete on ${props.hostname}`);
          } else {
            window.$toast?.error(`Scan failed on ${props.hostname}`, {
              details: job.error_summary || "See Job History for details",
            });
          }
          load();
        }
      } catch (e) {
        pollHandle?.pause();
        pollHandle = null;
        scanning.value = false;
        window.$toast?.error("Lost connection while polling scan status", e);
      }
    },
    2000,
    { immediate: true }
  );
}

async function upgradeDrv() {
  confirmDrv.value = false;
  try {
    await upgradeDrivers({ hosts: [props.hostname] });
    window.$toast?.success(`Driver upgrade started on ${props.hostname}`);
  } catch (e) {
    window.$toast?.error(`Couldn't start driver upgrade on ${props.hostname}`, e);
  }
}

async function handleDelete() {
  confirmDelete.value = false;
  try {
    await deleteHost(props.hostname);
    window.$toast?.success(`Removed ${props.hostname} from fleet`);
    router.push("/");
  } catch (e) {
    window.$toast?.error(`Couldn't delete ${props.hostname}`, e);
  }
}

function diskClass(pct) {
  if (!pct) return "good";
  if (pct >= 90) return "danger";
  if (pct >= 75) return "warn";
  return "good";
}

onMounted(load);
onUnmounted(() => {
  pollHandle?.pause();
  pollHandle = null;
});
</script>

<style scoped>
.info-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 14px;
  border-bottom: 1px solid var(--border-subtle);
}

.info-row:last-child {
  border-bottom: none;
}

.info-row span:first-child {
  color: var(--text-secondary);
  font-size: 13px;
}

.disk-row {
  display: flex;
  align-items: center;
  font-size: 14px;
}

.disk-row span {
  font-size: 13px;
  min-width: 40px;
}

.auth-toggle {
  margin-bottom: var(--space-sm);
}
</style>
