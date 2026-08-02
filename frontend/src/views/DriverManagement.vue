<template>
  <div>
    <div class="page-header">
      <h2>Driver Management</h2>
      <button class="btn btn-ghost btn-sm" type="button" aria-label="Refresh driver status" @click="load">
        <i class="fas fa-sync-alt" aria-hidden="true"></i> Refresh
      </button>
    </div>
    <PageIntro>
      Track GPU driver versions across the fleet and roll out upgrades. Pick a mode, select hosts, then upgrade — mismatches and reboot requirements are flagged below.
    </PageIntro>

    <div class="card" style="margin-bottom: var(--space-md)">
      <div class="card-body">
        <div class="flex gap-sm items-center flex-wrap">
          <div class="form-group" style="margin-bottom: 0">
            <label class="form-label" for="upgrade-mode">Upgrade Mode</label>
            <select id="upgrade-mode" v-model="upgradeMode" class="form-select" style="width: auto; min-width: 180px">
              <option value="standard">Standard (Patch)</option>
              <option value="major">Major Version</option>
            </select>
          </div>
          <div v-if="upgradeMode === 'major'" class="form-group" style="margin-bottom: 0">
            <label class="form-label" for="target-version">Target Driver Version</label>
            <input id="target-version" v-model="targetVersion" class="form-input" placeholder="e.g. 570, 580" style="width: 140px" />
          </div>
          <div style="align-self: flex-end">
            <button
              class="btn btn-green btn-sm"
              type="button"
              :disabled="!selectedHosts.length || (upgradeMode === 'major' && !targetVersion)"
              @click="askUpgrade"
            >
              <i class="fas fa-download" aria-hidden="true"></i>
              {{ upgradeMode === 'major' ? `Upgrade to ${targetVersion || '…'}` : 'Upgrade Selected' }}
            </button>
          </div>
        </div>
        <p style="font-size: 12px; color: var(--text-secondary); margin-top: var(--space-xs)">
          <template v-if="upgradeMode === 'standard'">
            Applies patch updates within the current driver branch using apt dist-upgrade (Spark) or apt upgrade (Workstation).
          </template>
          <template v-else>
            Installs a specific driver branch package (e.g. nvidia-driver-570). Firmware updates are handled separately in Maintenance.
          </template>
        </p>
        <button
          type="button"
          class="dm-ask"
          @click="askHelpChat('Which NVIDIA driver branch should I run on DGX Spark and Workstation right now?')"
        >
          <i class="fas fa-circle-question" aria-hidden="true"></i>
          Ask DGX Help: which driver branch should I pick?
        </button>
      </div>
    </div>

    <DriverDriftSummary :drivers="drivers" />

    <div v-if="drivers.length" class="table-wrapper">
      <table class="table-reflow">
        <thead>
          <tr>
            <th><input type="checkbox" :checked="allSelected" :aria-label="allSelected ? 'Deselect all' : 'Select all'" @change="toggleAll" /></th>
            <th>Hostname</th>
            <th>Machine Type</th>
            <th>Driver Version <InfoTooltip :text="GLOSSARY.driverBranch" /></th>
            <th>CUDA Version <InfoTooltip :text="GLOSSARY.cuda" /></th>
            <th>Reboot Required <InfoTooltip :text="GLOSSARY.rebootRequired" /></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in drivers" :key="d.hostname">
            <td data-label="Select">
              <input type="checkbox" :value="d.hostname" v-model="selectedHosts" :aria-label="`Select ${d.hostname}`" />
            </td>
            <td data-label="Hostname">
              <router-link :to="`/hosts/${d.hostname}`" style="font-weight: 500">{{ d.hostname }}</router-link>
            </td>
            <td data-label="Type">
              <span :class="['badge', getMachineType(d.machine_type).badge]">
                {{ getMachineType(d.machine_type).short }}
              </span>
            </td>
            <td data-label="Driver">{{ d.driver_version || '--' }}</td>
            <td data-label="CUDA">{{ d.cuda_version || '--' }}</td>
            <td data-label="Reboot">
              <span v-if="d.reboot_required" class="badge badge-red">Yes</span>
              <span v-else style="color: var(--text-secondary)">No</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="empty-state">
      <i class="fas fa-microchip" aria-hidden="true"></i>
      <p>No GPU-bearing hosts in fleet</p>
      <router-link to="/" class="btn btn-primary btn-sm" style="display: inline-flex">
        <i class="fas fa-plus" aria-hidden="true"></i> Add a host
      </router-link>
    </div>

    <ConfirmDialog
      :visible="confirmOpen"
      :title="`Upgrade drivers on ${selectedHosts.length} host${selectedHosts.length !== 1 ? 's' : ''}`"
      :message="upgradeMode === 'major'
        ? `Installing driver branch package nvidia-driver-${targetVersion} may replace driver packages and require a reboot. Existing GPU workloads will be interrupted.`
        : `Applying patch-level driver updates. May require a reboot depending on the package set. Active GPU workloads may be interrupted.`"
      confirm-text="Start upgrade"
      :danger-mode="true"
      :require-text="selectedHosts.length > 1 ? `UPGRADE ${selectedHosts.length}` : ''"
      @confirm="handleUpgrade"
      @cancel="confirmOpen = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { getDriverStatus, upgradeDrivers } from "../api.js";
import { getMachineType } from "../machineTypes.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import DriverDriftSummary from "../components/DriverDriftSummary.vue";
import InfoTooltip from "../components/InfoTooltip.vue";
import PageIntro from "../components/PageIntro.vue";
import { GLOSSARY } from "../glossary.js";
import { sortHostnames } from "../utils/hosts.js";

const drivers = ref([]);
const selectedHosts = ref([]);
const upgradeMode = ref("standard");
const targetVersion = ref("");
const confirmOpen = ref(false);

const allSelected = computed(
  () => drivers.value.length > 0 && selectedHosts.value.length === drivers.value.length
);

function toggleAll(e) {
  selectedHosts.value = e.target.checked ? drivers.value.map((d) => d.hostname) : [];
}

async function load() {
  try {
    const all = await getDriverStatus();
    drivers.value = all.filter((d) => getMachineType(d.machine_type).hasGpu);
  } catch (e) {
    window.$toast?.error("Couldn't load driver status", e);
  }
}

function askUpgrade() {
  if (!selectedHosts.value.length) return;
  confirmOpen.value = true;
}

async function handleUpgrade() {
  confirmOpen.value = false;
  try {
    const payload = {
      hosts: sortHostnames(selectedHosts.value),
      upgrade_mode: upgradeMode.value,
    };
    if (upgradeMode.value === "major" && targetVersion.value) {
      payload.target_driver_version = targetVersion.value;
    }
    const result = await upgradeDrivers(payload);
    window.$toast?.success(result?.detail || "Driver upgrade started");
    selectedHosts.value = [];
  } catch (e) {
    window.$toast?.error("Couldn't start driver upgrade", e);
  }
}

function askHelpChat(prompt) {
  window.dispatchEvent(new CustomEvent("helpchat:open", { detail: { prompt } }));
}

onMounted(load);
</script>

<style scoped>
.dm-ask {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--space-xs);
  padding: 4px 10px;
  background: transparent;
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-info);
  cursor: pointer;
  font-family: var(--font-family);
  transition: var(--transition-standard);
}
.dm-ask:hover { background: var(--surface-info-soft); border-color: var(--color-info); }
.dm-ask:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
</style>
