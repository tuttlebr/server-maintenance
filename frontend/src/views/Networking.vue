<template>
  <div>
    <div class="page-header">
      <h2>Networking</h2>
      <button class="btn btn-ghost btn-sm" aria-label="Refresh networking status" @click="load">
        <i class="fas fa-sync-alt" aria-hidden="true"></i> Refresh
      </button>
    </div>
    <PageIntro>
      Network interface speeds and Fabric Manager status per host. Fabric Manager runs on multi-GPU workstations and controls the NVLink/NVSwitch fabric — only restart it during a maintenance window.
    </PageIntro>

    <div v-if="networking.length" class="table-wrapper">
      <table class="table-reflow">
        <thead>
          <tr>
            <th>Hostname</th>
            <th>Machine Type</th>
            <th>NIC Type</th>
            <th>NIC Speed <InfoTooltip :text="GLOSSARY.nicSpeed" /></th>
            <th>Fabric Manager <InfoTooltip :text="GLOSSARY.fabricManager" /></th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="n in networking" :key="n.hostname">
            <td data-label="Hostname">
              <router-link :to="`/hosts/${n.hostname}`" style="font-weight: 500">{{ n.hostname }}</router-link>
            </td>
            <td data-label="Type">
              <span :class="['badge', getMachineType(n.machine_type).badge]">
                {{ getMachineType(n.machine_type).short }}
              </span>
            </td>
            <td data-label="NIC">{{ n.nic_type || '--' }}</td>
            <td data-label="Speed">{{ n.nic_speed || '--' }}</td>
            <td data-label="Fabric Manager">
              <StatusBadge v-if="getMachineType(n.machine_type).hasFabricManager" :status="fmStatus(n.fabric_manager_status)" with-tooltip />
              <span v-else class="muted">--</span>
            </td>
            <td data-label="Actions">
              <div v-if="getMachineType(n.machine_type).hasFabricManager" class="flex gap-xs">
                <button
                  class="btn btn-ghost btn-sm btn-icon"
                  :aria-label="`Start fabric manager on ${n.hostname}`"
                  title="Start"
                  @click="askConfirm('started', n.hostname)"
                >
                  <i class="fas fa-play" aria-hidden="true"></i>
                </button>
                <button
                  class="btn btn-ghost btn-sm btn-icon"
                  :aria-label="`Stop fabric manager on ${n.hostname}`"
                  title="Stop"
                  @click="askConfirm('stopped', n.hostname)"
                >
                  <i class="fas fa-stop" aria-hidden="true"></i>
                </button>
                <button
                  class="btn btn-ghost btn-sm btn-icon"
                  :aria-label="`Restart fabric manager on ${n.hostname}`"
                  title="Restart"
                  @click="askConfirm('restarted', n.hostname)"
                >
                  <i class="fas fa-redo" aria-hidden="true"></i>
                </button>
              </div>
              <span v-else class="muted">--</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else-if="!loading" class="empty-state">
      <i class="fas fa-network-wired" aria-hidden="true"></i>
      <p>No hosts in fleet</p>
      <router-link to="/" class="btn btn-primary btn-sm" style="display: inline-flex">
        <i class="fas fa-plus" aria-hidden="true"></i> Add a host
      </router-link>
    </div>
    <div v-else class="table-wrapper">
      <SkeletonRow v-for="i in 4" :key="i" :widths="['140px', '60px', '120px', '60px', '90px', '120px']" />
    </div>

    <ConfirmDialog
      :visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :confirm-text="confirm.confirmText"
      :danger-mode="confirm.danger"
      :require-text="confirm.requireText"
      @confirm="runConfirmed"
      @cancel="confirm.visible = false"
    />
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from "vue";
import { getNetworkingStatus, manageFabricManager } from "../api.js";
import StatusBadge from "../components/StatusBadge.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import SkeletonRow from "../components/SkeletonRow.vue";
import InfoTooltip from "../components/InfoTooltip.vue";
import PageIntro from "../components/PageIntro.vue";
import { getMachineType } from "../machineTypes.js";
import { GLOSSARY } from "../glossary.js";

const networking = ref([]);
const loading = ref(true);

const confirm = reactive({
  visible: false,
  title: "",
  message: "",
  confirmText: "Confirm",
  danger: true,
  requireText: "",
  action: null,
  hostname: null,
});

function fmStatus(status) {
  if (status === "active") return "online";
  if (status === "inactive" || status === "dead") return "offline";
  return "unknown";
}

async function load() {
  loading.value = true;
  try {
    networking.value = await getNetworkingStatus();
  } catch (e) {
    window.$toast?.error("Couldn't load networking status", e);
  } finally {
    loading.value = false;
  }
}

function askConfirm(action, hostname) {
  const verbs = { started: "Start", stopped: "Stop", restarted: "Restart" };
  const verb = verbs[action] || action;
  const isDestructive = action === "stopped" || action === "restarted";
  confirm.title = `${verb} fabric manager on ${hostname}`;
  confirm.message =
    action === "stopped"
      ? `Stopping fabric manager will interrupt NVLink fabric on ${hostname}. Active GPU workloads using the fabric will fail. This action is rarely safe outside of maintenance windows.`
      : action === "restarted"
      ? `Restarting fabric manager will briefly disconnect the NVLink fabric on ${hostname}. Active GPU workloads may experience errors. Proceed only when no critical jobs are running.`
      : `Start fabric manager on ${hostname}. Safe if the service is currently inactive.`;
  confirm.confirmText = `${verb} fabric manager`;
  confirm.danger = isDestructive;
  confirm.requireText = action === "stopped" ? hostname : "";
  confirm.action = action;
  confirm.hostname = hostname;
  confirm.visible = true;
}

async function runConfirmed() {
  confirm.visible = false;
  const { action, hostname } = confirm;
  if (!action || !hostname) return;
  try {
    await manageFabricManager(action, { hosts: [hostname] });
    const verbs = { started: "Starting", stopped: "Stopping", restarted: "Restarting" };
    window.$toast?.success(`${verbs[action]} fabric manager on ${hostname}`);
  } catch (e) {
    window.$toast?.error(`Couldn't ${action.replace(/ed$/, "")} fabric manager on ${hostname}`, e);
  }
}

onMounted(load);
</script>

<style scoped>
.muted {
  color: var(--text-muted);
}
</style>
