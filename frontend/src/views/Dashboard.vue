<template>
  <div>
    <div class="page-header">
      <h2>Fleet Dashboard</h2>
      <div class="flex gap-xs">
        <button class="btn btn-ghost btn-sm" :disabled="store.loading" @click="refresh">
          <i :class="['fas', store.loading ? 'fa-spinner fa-spin' : 'fa-sync-alt']" aria-hidden="true"></i>
          {{ store.loading ? 'Refreshing…' : 'Refresh' }}
        </button>
        <button class="btn btn-green btn-sm" @click="scanAll">
          <i class="fas fa-satellite-dish" aria-hidden="true"></i> Scan Fleet
        </button>
        <button class="btn btn-primary btn-sm" @click="showAddHost = true">
          <i class="fas fa-plus" aria-hidden="true"></i> Add Host
        </button>
      </div>
    </div>

    <!-- Fleet Status Hero -->
    <div class="fleet-hero">
      <div class="fleet-hero-grid">
        <div class="fleet-hero-headline">
          <div class="fleet-headline-label">Fleet</div>
          <div class="fleet-headline-value">
            <span>{{ hosts.length }}</span>
            <small>hosts</small>
          </div>
          <div v-if="store.lastUpdated" class="fleet-headline-updated">
            <span class="dot dot-green dot-pulse" v-if="!store.loading" aria-hidden="true"></span>
            <span class="dot dot-gray" v-else aria-hidden="true"></span>
            updated {{ relativeTime(store.lastUpdated) }}
          </div>
        </div>
        <div class="fleet-hero-bar">
          <div class="fleet-bar-track" :aria-label="`Fleet status: ${onlineCount} online, ${offlineCount} offline, ${unknownCount} unknown`">
            <div class="fleet-bar-seg fleet-bar-online" :style="{ flex: onlineCount }" v-if="onlineCount"></div>
            <div class="fleet-bar-seg fleet-bar-offline" :style="{ flex: offlineCount }" v-if="offlineCount"></div>
            <div class="fleet-bar-seg fleet-bar-unknown" :style="{ flex: unknownCount }" v-if="unknownCount"></div>
            <div v-if="!hosts.length" class="fleet-bar-seg fleet-bar-empty"></div>
          </div>
          <div class="fleet-bar-legend">
            <span><span class="dot dot-green" aria-hidden="true"></span> {{ onlineCount }} Online</span>
            <span><span class="dot dot-red" aria-hidden="true"></span> {{ offlineCount }} Offline</span>
            <span v-if="unknownCount"><span class="dot dot-gray" aria-hidden="true"></span> {{ unknownCount }} Unknown</span>
            <span v-if="rebootCount"><span class="dot dot-orange" aria-hidden="true"></span> {{ rebootCount }} Reboot needed</span>
          </div>
        </div>
        <div class="fleet-hero-jobs">
          <div class="fleet-headline-label">Active jobs</div>
          <div class="fleet-jobs-value">
            <span :class="store.activeJobs.length ? 'fleet-jobs-running' : ''">{{ store.activeJobs.length }}</span>
            <small v-if="recentJobs.length"> · {{ recentJobs.length }} recent</small>
          </div>
          <router-link v-if="store.activeJobs.length" to="/jobs" class="fleet-jobs-link">
            <i class="fas fa-arrow-right" aria-hidden="true"></i> View running jobs
          </router-link>
        </div>
      </div>
    </div>

    <!-- Quick Answers -->
    <section class="quick-answers" aria-label="Fleet quick answers">
      <div class="quick-card">
        <div class="quick-card-header">
          <div>
            <div class="quick-label">GPU usage now</div>
            <div class="quick-value">
              <template v-if="overview?.gpu?.last_scanned_at">
                {{ overview.gpu.free_gpus }} free
                <span>{{ overview.gpu.active_gpus }} active</span>
                <span v-if="overview.gpu.idle_gpus">{{ overview.gpu.idle_gpus }} idle</span>
              </template>
              <template v-else>No scan yet</template>
            </div>
          </div>
          <span :class="['badge', reportBadgeClass(overview?.gpu)]">
            {{ reportAgeLabel(overview?.gpu) }}
          </span>
        </div>
        <div v-if="topGpuUsers.length" class="quick-list">
          <div v-for="u in topGpuUsers" :key="u.user" class="quick-row">
            <span>{{ u.user }}</span>
            <strong>{{ u.gpu_count }} GPU{{ u.gpu_count === 1 ? '' : 's' }}</strong>
          </div>
        </div>
        <p v-else class="quick-empty">No active GPU owners in the last report.</p>
        <div class="quick-actions">
          <button class="btn btn-primary btn-sm" type="button" :disabled="quickActionRunning === 'gpu'" @click="startGpuUsageScan">
            <i :class="['fas', quickActionRunning === 'gpu' ? 'fa-spinner fa-spin' : 'fa-microchip']" aria-hidden="true"></i>
            Scan GPUs
          </button>
          <router-link to="/maintenance#gpu" class="btn btn-ghost btn-sm">Details</router-link>
        </div>
      </div>

      <div class="quick-card">
        <div class="quick-card-header">
          <div>
            <div class="quick-label">Disk cleanup owners</div>
            <div class="quick-value">
              <template v-if="overview?.storage?.owners?.length">
                {{ formatSize(overview.storage.owners[0].size_mb) }}
                <span>{{ overview.storage.owners[0].owner_user || 'unknown owner' }}</span>
              </template>
              <template v-else>No report yet</template>
            </div>
          </div>
          <span :class="['badge', reportBadgeClass(overview?.storage)]">
            {{ reportAgeLabel(overview?.storage) }}
          </span>
        </div>
        <div v-if="topStorageOwners.length" class="quick-list">
          <div v-for="entry in topStorageOwners" :key="`${entry.hostname}-${entry.path}`" class="quick-row">
            <span :title="entry.path">{{ entry.owner_user || entry.path }}</span>
            <strong>{{ formatSize(entry.size_mb) }}</strong>
          </div>
        </div>
        <p v-else class="quick-empty">Run storage analysis to see who owns the largest directories.</p>
        <div class="quick-actions">
          <button class="btn btn-primary btn-sm" type="button" :disabled="quickActionRunning === 'storage'" @click="startStorageAnalysis">
            <i :class="['fas', quickActionRunning === 'storage' ? 'fa-spinner fa-spin' : 'fa-hdd']" aria-hidden="true"></i>
            Analyze Storage
          </button>
          <router-link to="/maintenance#storage" class="btn btn-ghost btn-sm">Details</router-link>
        </div>
      </div>

      <div class="quick-card">
        <div class="quick-card-header">
          <div>
            <div class="quick-label">Maintenance queue</div>
            <div class="quick-value">
              {{ queueCount }} item{{ queueCount === 1 ? '' : 's' }}
              <span v-if="store.activeJobs.length">{{ store.activeJobs.length }} running</span>
            </div>
          </div>
          <router-link to="/maintenance" class="quick-icon-link" aria-label="Open maintenance">
            <i class="fas fa-chevron-right" aria-hidden="true"></i>
          </router-link>
        </div>
        <div v-if="queueItems.length" class="quick-list">
          <div v-for="item in queueItems" :key="item.label" class="quick-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.count }}</strong>
          </div>
        </div>
        <p v-else class="quick-empty">No routine maintenance is queued from current scans.</p>
        <div class="quick-actions">
          <button class="btn btn-green btn-sm" type="button" @click="scanAll">
            <i class="fas fa-satellite-dish" aria-hidden="true"></i> Scan Fleet
          </button>
          <router-link to="/jobs" class="btn btn-ghost btn-sm">Jobs</router-link>
        </div>
      </div>
    </section>

    <!-- Post-add scan nudge -->
    <div v-if="lastAddedHosts.length" class="callout callout-info" style="margin-top: var(--space-md)">
      <i class="fas fa-satellite-dish callout-icon" aria-hidden="true"></i>
      <div class="callout-body">
        <div class="callout-title">
          {{ lastAddedHosts.length === 1 ? `${lastAddedHosts[0]} added` : `${lastAddedHosts.length} hosts added` }}
        </div>
        <div style="font-size: 12px; color: var(--text-secondary)">
          Run Scan Fleet to populate GPU, driver, disk, and network info.
        </div>
      </div>
      <div class="callout-actions">
        <button class="btn btn-green btn-sm" type="button" @click="scanAll">
          <i class="fas fa-satellite-dish" aria-hidden="true"></i> Scan now
        </button>
        <button class="btn btn-ghost btn-sm" type="button" aria-label="Dismiss" @click="dismissScanNudge">
          Dismiss
        </button>
      </div>
    </div>

    <!-- Fleet Needs Attention -->
    <NeedsAttention v-if="store.hasLoadedOnce" :hosts="hosts" />

    <!-- Fleet Grid -->
    <h3 style="margin-bottom: var(--space-sm); margin-top: var(--space-md)">Fleet</h3>
    <div v-if="hosts.length" class="grid-cards">
      <FleetCard v-for="h in hosts" :key="h.hostname" :host="h" />
    </div>
    <div v-else-if="!store.hasLoadedOnce" class="grid-cards">
      <div v-for="i in 4" :key="i" class="card">
        <div class="card-body">
          <SkeletonRow :widths="['80px', '40px']" :height="18" :gap="10" />
          <SkeletonRow :widths="['120px', '60px']" :height="12" :gap="10" />
          <SkeletonRow :widths="['100%']" :height="8" :gap="0" />
        </div>
      </div>
    </div>
    <div v-else class="empty-state">
      <i class="fas fa-server" aria-hidden="true"></i>
      <p>No hosts in fleet yet</p>
      <button class="btn btn-primary btn-sm" type="button" @click="showAddHost = true">
        <i class="fas fa-plus" aria-hidden="true"></i> Add your first host
      </button>
    </div>

    <!-- Recent Jobs -->
    <h3 style="margin-top: var(--space-md); margin-bottom: var(--space-sm)">Recent Jobs</h3>
    <div v-if="recentJobs.length" class="table-wrapper">
      <table class="table-reflow">
        <thead>
          <tr>
            <th>Playbook</th>
            <th>Hosts</th>
            <th>Status</th>
            <th>Duration</th>
            <th>When</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in recentJobs.slice(0, 6)" :key="job.job_id" style="cursor: pointer" @click="$router.push('/jobs')">
            <td data-label="Playbook">{{ job.playbook }}</td>
            <td data-label="Hosts">{{ formatHostList(job.target_hosts) }}</td>
            <td data-label="Status"><StatusBadge :status="job.status" /></td>
            <td data-label="Duration">{{ job.duration_seconds ? job.duration_seconds + 's' : '--' }}</td>
            <td data-label="When" :title="formatLongTime(job.created_at)">{{ relativeTime(job.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="empty-state" style="padding: var(--space-md)">
      <p>No jobs yet</p>
    </div>

    <!-- Add Host Modal -->
    <BaseModal :visible="showAddHost" title="Add Hosts" size="lg" @cancel="closeAddHost">
      <template v-if="!enrollmentPreview">
      <div class="tabs" style="margin-bottom: var(--space-sm)">
        <button :class="['tab', { active: addTab === 'single' }]" type="button" @click="addTab = 'single'">Single Host</button>
        <button :class="['tab', { active: addTab === 'bulk' }]" type="button" @click="addTab = 'bulk'">Bulk Import</button>
      </div>

      <!-- Single Host Tab -->
      <form v-if="addTab === 'single'" id="add-host-form" @submit.prevent="handleAddHost">
        <div class="form-group">
          <label class="form-label" for="add-hostname">Hostname</label>
          <input id="add-hostname" v-model="newHost.hostname" class="form-input" placeholder="ast-spark-02" required />
        </div>
        <div class="form-group">
          <label class="form-label" for="add-ip">IP Address</label>
          <input id="add-ip" v-model="newHost.ip_address" class="form-input" placeholder="10.0.0.2" />
        </div>
        <div class="form-group">
          <label class="form-label" for="add-type">Machine Type</label>
          <select id="add-type" v-model="newHost.machine_type" class="form-select">
            <option v-for="(mt, key) in MACHINE_TYPES" :key="key" :value="key">{{ mt.label }}</option>
          </select>
        </div>
        <div class="separator"></div>
        <h4 style="margin-bottom: var(--space-xs); font-size: 13px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px">
          SSH Credentials
        </h4>
        <div class="form-group">
          <label class="form-label" for="add-user">SSH Username</label>
          <input id="add-user" v-model="newHost.ansible_user" class="form-input" placeholder="brandon" required />
          <small class="form-help">The existing Linux account Ansible will use on the remote host. This is not the container's fleet user.</small>
        </div>
        <label class="checkbox-label auth-toggle">
          <input type="checkbox" v-model="newHost.passwordless_ssh" @change="onPasswordlessToggle(newHost)" />
          Dedicated fleet SSH key
        </label>
        <div v-if="!newHost.passwordless_ssh" class="form-group">
          <label class="form-label" for="add-pw">SSH Password</label>
          <input
            id="add-pw"
            v-model="newHost.ansible_password"
            type="password"
            class="form-input"
            placeholder="Enter SSH password"
          />
        </div>
        <div v-else class="form-group">
          <label class="form-label" for="add-bootstrap-pw">One-time bootstrap password (optional)</label>
          <input
            id="add-bootstrap-pw"
            v-model="newHost.bootstrap_password"
            type="password"
            class="form-input"
            placeholder="Install the fleet key automatically"
          />
          <small class="form-help">Leave blank if the fleet agent's public key is already authorized for this SSH user. This password is never stored.</small>
        </div>
        <div class="form-group">
          <label class="form-label" for="add-sudo">Sudo Password (optional)</label>
          <input
            id="add-sudo"
            v-model="newHost.ansible_become_password"
            type="password"
            class="form-input"
            :placeholder="newHost.passwordless_ssh ? 'Leave blank for passwordless sudo' : 'Leave blank if sudo does not prompt'"
          />
        </div>
      </form>

      <!-- Bulk Import Tab -->
      <div v-if="addTab === 'bulk'">
        <div
          class="upload-zone"
          :class="{ dragover: csvDragover }"
          role="button"
          tabindex="0"
          @dragover.prevent="csvDragover = true"
          @dragleave="csvDragover = false"
          @drop.prevent="onCsvDrop"
          @click="$refs.csvInput.click()"
          @keydown.enter.prevent="$refs.csvInput.click()"
        >
          <i class="fas fa-cloud-upload-alt" aria-hidden="true"></i>
          <p>Drag and drop a CSV file, or click to browse</p>
          <p style="font-size: 12px; margin-top: 4px; color: var(--text-secondary)">
            Columns: hostname, ip_address, machine_type, ansible_user, ansible_password, ansible_become_password, passwordless_ssh, bootstrap_password
          </p>
          <input ref="csvInput" type="file" accept=".csv,text/csv" style="display: none" @change="onCsvSelect" />
        </div>

        <div v-if="csvErrors.length" class="csv-warnings">
          <strong><i class="fas fa-exclamation-triangle" aria-hidden="true"></i> {{ csvErrors.length }} row{{ csvErrors.length !== 1 ? 's' : '' }} skipped:</strong>
          <ul>
            <li v-for="(err, i) in csvErrors.slice(0, 6)" :key="i">Row {{ err.row }}: {{ err.message }}</li>
            <li v-if="csvErrors.length > 6">…and {{ csvErrors.length - 6 }} more</li>
          </ul>
        </div>

        <div v-if="csvHosts.length" style="margin-top: var(--space-sm)">
          <h4 style="margin-bottom: var(--space-xs)">Preview ({{ csvHosts.length }} host{{ csvHosts.length !== 1 ? 's' : '' }})</h4>
          <div class="table-wrapper" style="max-height: 260px; overflow-y: auto">
            <table>
              <thead>
                <tr>
                  <th>Hostname</th>
                  <th>IP Address</th>
                  <th>Type</th>
                  <th>SSH User</th>
                  <th>SSH Auth</th>
                  <th>Password</th>
                  <th>Bootstrap</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(h, i) in csvHosts" :key="i">
                  <td>{{ h.hostname }}</td>
                  <td>{{ h.ip_address || '--' }}</td>
                  <td><span :class="['badge', getMachineType(h.machine_type).badge]">{{ getMachineType(h.machine_type).short }}</span></td>
                  <td>{{ h.ansible_user || '--' }}</td>
                  <td>{{ h.passwordless_ssh ? 'Key' : 'Password' }}</td>
                  <td>{{ h.ansible_password ? '***' : '--' }}</td>
                  <td>{{ h.bootstrap_password ? 'one-time' : '--' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      </template>

      <div v-else>
        <div :class="['callout', enrollmentPreview.agent.ready ? 'callout-success' : 'callout-danger']">
          <i class="fas fa-key callout-icon" aria-hidden="true"></i>
          <div class="callout-body">
            <div class="callout-title">Dedicated fleet SSH agent</div>
            <div class="enrollment-detail">{{ enrollmentPreview.agent.detail }}</div>
            <code v-if="enrollmentPreview.agent.fingerprints?.length">
              {{ enrollmentPreview.agent.fingerprints.join(", ") }}
            </code>
          </div>
        </div>

        <div class="callout callout-warn" style="margin-top: var(--space-sm)">
          <i class="fas fa-shield-alt callout-icon" aria-hidden="true"></i>
          <div class="callout-body">
            <div class="callout-title">Verify host identities</div>
            <div class="enrollment-detail">
              Compare these ED25519 fingerprints with each host's console. Approving records the keys in the managed trust database, then verifies SSH authentication before saving any host.
            </div>
          </div>
        </div>

        <div class="table-wrapper enrollment-table">
          <table>
            <thead>
              <tr>
                <th>Host</th>
                <th>Address</th>
                <th>Host key</th>
                <th>Trust</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="host in enrollmentPreview.hosts" :key="host.hostname">
                <td>{{ host.hostname }}</td>
                <td>{{ host.address }}</td>
                <td><code>{{ host.fingerprint || host.detail }}</code></td>
                <td>
                  <span :class="['badge', enrollmentStatusClass(host)]">
                    {{ host.already_exists ? 'Already added' : host.trust_status }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="enrollmentFailures.length" class="csv-warnings">
          <strong><i class="fas fa-exclamation-triangle" aria-hidden="true"></i> Enrollment failures:</strong>
          <ul>
            <li v-for="failure in enrollmentFailures" :key="failure.hostname">
              {{ failure.hostname }}: {{ failure.detail }}
            </li>
          </ul>
        </div>
      </div>

      <template #actions>
        <template v-if="enrollmentPreview">
          <button type="button" class="btn btn-ghost" data-cancel :disabled="enrollmentSubmitting" @click="resetEnrollmentPreview">Back</button>
          <button type="button" class="btn btn-green" :disabled="!enrollmentPreview.ready || enrollmentSubmitting" @click="approveEnrollment">
            <i class="fas fa-shield-alt" aria-hidden="true"></i>
            {{ enrollmentSubmitting ? 'Verifying…' : 'Approve, verify & add' }}
          </button>
        </template>
        <template v-else>
          <button type="button" class="btn btn-ghost" data-cancel @click="closeAddHost">Cancel</button>
          <button v-if="addTab === 'single'" type="submit" form="add-host-form" class="btn btn-green" :disabled="enrollmentLoading">
            <i class="fas fa-search" aria-hidden="true"></i> {{ enrollmentLoading ? 'Checking SSH…' : 'Verify SSH & Add' }}
          </button>
          <button v-else type="button" class="btn btn-green" :disabled="!csvHosts.length || enrollmentLoading" @click="handleBulkAdd">
            <i class="fas fa-search" aria-hidden="true"></i>
            {{ enrollmentLoading ? 'Checking SSH…' : `Verify & import ${csvHosts.length} host${csvHosts.length !== 1 ? 's' : ''}` }}
          </button>
        </template>
      </template>
    </BaseModal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import Papa from "papaparse";
import {
  enrollHosts,
  getMaintenanceOverview,
  previewHostEnrollment,
  runGpuUsage,
  runStorageAnalysis,
  scanAllHosts,
} from "../api.js";
import { useHostsStore } from "../stores/hosts.js";
import FleetCard from "../components/FleetCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import SkeletonRow from "../components/SkeletonRow.vue";
import BaseModal from "../components/BaseModal.vue";
import NeedsAttention from "../components/NeedsAttention.vue";
import { getMachineType, MACHINE_TYPES } from "../machineTypes.js";
import { relativeTime, formatLongTime } from "../utils/time.js";
import { formatHostList, sortByHostname, sortHostnames } from "../utils/hosts.js";

const store = useHostsStore();
const hosts = computed(() => store.hosts);
const recentJobs = computed(() => store.recentJobs);

const showAddHost = ref(false);
const addTab = ref("single");
const emptyHost = () => ({
  hostname: "",
  ip_address: "",
  machine_type: "unknown",
  ansible_user: "",
  ansible_password: "",
  ansible_become_password: "",
  bootstrap_password: "",
  passwordless_ssh: true,
});
const newHost = ref(emptyHost());
const csvHosts = ref([]);
const csvErrors = ref([]);
const csvDragover = ref(false);
const enrollmentPreview = ref(null);
const pendingEnrollmentHosts = ref([]);
const enrollmentFailures = ref([]);
const enrollmentLoading = ref(false);
const enrollmentSubmitting = ref(false);
const lastAddedHosts = ref([]);
const overview = ref(null);
const quickActionRunning = ref("");
let scanNudgeTimer = null;

const onlineCount = computed(() => hosts.value.filter((h) => h.status === "online").length);
const offlineCount = computed(() => hosts.value.filter((h) => h.status === "offline").length);
const unknownCount = computed(() => hosts.value.length - onlineCount.value - offlineCount.value);
const rebootCount = computed(() => hosts.value.filter((h) => h.reboot_required).length);
const topGpuUsers = computed(() => overview.value?.gpu?.users?.slice(0, 3) || []);
const topStorageOwners = computed(() => overview.value?.storage?.owners?.slice(0, 3) || []);
const queueItems = computed(() => {
  const fleet = overview.value?.fleet || {};
  const items = [];
  const reboot = fleet.reboot_required_hosts?.length || 0;
  const disk = fleet.high_disk_hosts?.length || 0;
  const stale = fleet.stale_hosts?.length || 0;
  const offline = (fleet.offline_hosts || 0) + (fleet.unknown_hosts || 0);
  if (reboot) items.push({ label: "Reboots needed", count: reboot });
  if (disk) items.push({ label: "High disk hosts", count: disk });
  if (stale) items.push({ label: "Stale scans", count: stale });
  if (offline) items.push({ label: "Offline or unknown", count: offline });
  return items;
});
const queueCount = computed(() => queueItems.value.reduce((sum, item) => sum + item.count, 0));

async function refresh() {
  try {
    await Promise.all([store.refresh({ force: true }), loadOverview()]);
  } catch (e) {
    window.$toast?.error("Couldn't refresh fleet status", e);
  }
}

async function loadOverview() {
  try {
    overview.value = await getMaintenanceOverview();
  } catch (e) {
    // Keep the dashboard usable if the optional overview fails.
    overview.value = null;
  }
}

async function scanAll() {
  try {
    await scanAllHosts();
    window.$toast?.success("Fleet scan started");
    dismissScanNudge();
  } catch (e) {
    window.$toast?.error("Couldn't start fleet scan", e);
  }
}

async function startGpuUsageScan() {
  quickActionRunning.value = "gpu";
  try {
    await runGpuUsage({ all_hosts: true });
    window.$toast?.success("GPU usage scan started");
    await loadOverview();
  } catch (e) {
    window.$toast?.error("Couldn't start GPU usage scan", e);
  } finally {
    quickActionRunning.value = "";
  }
}

async function startStorageAnalysis() {
  quickActionRunning.value = "storage";
  try {
    await runStorageAnalysis({ all_hosts: true });
    window.$toast?.success("Storage analysis started");
    await loadOverview();
  } catch (e) {
    window.$toast?.error("Couldn't start storage analysis", e);
  } finally {
    quickActionRunning.value = "";
  }
}

function reportAgeLabel(report) {
  if (!report?.last_scanned_at) return "No report";
  return `${report.stale ? "Stale" : "Fresh"} · ${relativeTime(report.last_scanned_at)}`;
}

function reportBadgeClass(report) {
  if (!report?.last_scanned_at) return "badge-outline";
  return report.stale ? "badge-orange" : "badge-green";
}

function formatSize(mb) {
  const val = parseInt(mb) || 0;
  if (val >= 1024 * 1024) return (val / (1024 * 1024)).toFixed(1) + " TB";
  if (val >= 1024) return (val / 1024).toFixed(1) + " GB";
  return val + " MB";
}

function showScanNudge(hostnames) {
  lastAddedHosts.value = sortHostnames(hostnames);
  clearTimeout(scanNudgeTimer);
  scanNudgeTimer = setTimeout(dismissScanNudge, 60_000);
}
function dismissScanNudge() {
  lastAddedHosts.value = [];
  clearTimeout(scanNudgeTimer);
  scanNudgeTimer = null;
}

async function handleAddHost() {
  if (!newHost.value.ansible_user) {
    window.$toast?.error("Enter the remote SSH username");
    return;
  }
  if (!newHost.value.passwordless_ssh && !newHost.value.ansible_password) {
    window.$toast?.error("Enter an SSH password or use the dedicated fleet SSH key");
    return;
  }
  await prepareEnrollment([hostPayload(newHost.value)]);
}

const COL_ALIASES = {
  hostname: ["hostname", "host", "name"],
  ip_address: ["ip_address", "ip", "address", "ansible_host"],
  machine_type: ["machine_type", "type"],
  ansible_user: ["ansible_user", "ssh_user", "user", "username"],
  ansible_password: ["ansible_password", "ssh_password", "password", "ssh_pass"],
  ansible_become_password: ["ansible_become_password", "sudo_password", "become_password", "become_pass"],
  bootstrap_password: ["bootstrap_password", "one_time_password", "enrollment_password"],
  passwordless_ssh: ["passwordless_ssh", "ssh_passwordless", "passwordless", "key_based_auth", "key_auth", "ssh_key", "ssh_auth_method", "auth_method"],
};

function normalizeFieldKeys(row) {
  const out = {};
  for (const [field, aliases] of Object.entries(COL_ALIASES)) {
    for (const a of aliases) {
      const k = Object.keys(row).find((kk) => kk.toLowerCase().trim() === a);
      if (k && row[k] != null && row[k] !== "") {
        out[field] = String(row[k]).trim();
        break;
      }
    }
  }
  return out;
}

const IP_REGEX = /^(\d{1,3}\.){3}\d{1,3}$/;
const HOST_REGEX = /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;
const PASSWORDLESS_TRUE = new Set(["1", "true", "yes", "y", "on", "key", "keys", "ssh_key", "publickey", "public_key", "passwordless"]);
const PASSWORDLESS_FALSE = new Set(["0", "false", "no", "n", "off", "password", "ssh_password", "password_auth"]);

function parsePasswordless(value) {
  if (value == null || value === "") return { valid: true, value: null };
  const normalized = String(value).trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
  if (!normalized) return { valid: true, value: null };
  if (PASSWORDLESS_TRUE.has(normalized)) return { valid: true, value: true };
  if (PASSWORDLESS_FALSE.has(normalized)) return { valid: true, value: false };
  return { valid: false, value: null };
}

function onPasswordlessToggle(host) {
  if (host.passwordless_ssh) host.ansible_password = "";
  else host.bootstrap_password = "";
}

function hostPayload(host) {
  const payload = { ...host, passwordless_ssh: !!host.passwordless_ssh };
  if (payload.passwordless_ssh) payload.ansible_password = "";
  else payload.bootstrap_password = "";
  return payload;
}

function parseCsv(text) {
  csvErrors.value = [];
  const parsed = Papa.parse(text, {
    header: true,
    skipEmptyLines: "greedy",
    transformHeader: (h) => h.toLowerCase().trim(),
  });

  let rows = parsed.data;
  // Fall back to a header-less parse if Papa didn't find headers we recognize.
  const seenKeys = new Set(rows.length ? Object.keys(rows[0]) : []);
  const knownHeaders = Object.values(COL_ALIASES).flat();
  const looksHeaderless = !rows.length || ![...seenKeys].some((k) => knownHeaders.includes(k));
  if (looksHeaderless) {
    const fallback = Papa.parse(text, { header: false, skipEmptyLines: "greedy" });
    rows = fallback.data.map((cols) => ({
      hostname: cols[0],
      ip_address: cols[1],
      machine_type: cols[2],
      ansible_user: cols[3],
      ansible_password: cols[4],
      ansible_become_password: cols[5],
      passwordless_ssh: cols[6],
      bootstrap_password: cols[7],
    }));
  }

  const good = [];
  rows.forEach((row, idx) => {
    const normalized = normalizeFieldKeys(row);
    const rowNumber = idx + 1 + (looksHeaderless ? 0 : 1); // +1 for header row when applicable

    if (!normalized.hostname) {
      csvErrors.value.push({ row: rowNumber, message: "missing hostname" });
      return;
    }
    if (!HOST_REGEX.test(normalized.hostname)) {
      csvErrors.value.push({ row: rowNumber, message: `invalid hostname "${normalized.hostname}"` });
      return;
    }
    if (normalized.ip_address && !IP_REGEX.test(normalized.ip_address)) {
      csvErrors.value.push({ row: rowNumber, message: `invalid IP "${normalized.ip_address}"` });
      return;
    }
    if (!normalized.machine_type) normalized.machine_type = "unknown";
    if (!normalized.ansible_user) {
      csvErrors.value.push({ row: rowNumber, message: "missing remote SSH username" });
      return;
    }
    const passwordless = parsePasswordless(normalized.passwordless_ssh);
    if (!passwordless.valid) {
      csvErrors.value.push({ row: rowNumber, message: `invalid passwordless_ssh value "${normalized.passwordless_ssh}"` });
      return;
    }
    const passwordlessSsh = passwordless.value ?? !normalized.ansible_password;
    if (!passwordlessSsh && !normalized.ansible_password) {
      csvErrors.value.push({ row: rowNumber, message: "missing SSH password for password auth" });
      return;
    }
    good.push({
      hostname: normalized.hostname,
      ip_address: normalized.ip_address || "",
      machine_type: normalized.machine_type,
      ansible_user: normalized.ansible_user || "",
      ansible_password: passwordlessSsh ? "" : normalized.ansible_password || "",
      ansible_become_password: normalized.ansible_become_password || "",
      bootstrap_password: passwordlessSsh ? normalized.bootstrap_password || "" : "",
      passwordless_ssh: passwordlessSsh,
    });
  });

  return sortByHostname(good);
}

function handleCsvFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".csv") && file.type !== "text/csv") {
    window.$toast?.error("Couldn't read file — please upload a .csv");
    return;
  }
  const reader = new FileReader();
  reader.onload = (e) => {
    csvHosts.value = parseCsv(String(e.target.result));
    if (csvHosts.value.length === 0 && csvErrors.value.length === 0) {
      window.$toast?.error("Couldn't parse CSV — no valid rows found");
    } else if (csvErrors.value.length) {
      window.$toast?.info(`Parsed ${csvHosts.value.length} host(s); ${csvErrors.value.length} skipped`);
    }
  };
  reader.onerror = () => window.$toast?.error("Couldn't read file");
  reader.readAsText(file);
}

function onCsvDrop(e) {
  csvDragover.value = false;
  handleCsvFile(e.dataTransfer.files[0]);
}

function onCsvSelect(e) {
  handleCsvFile(e.target.files[0]);
}

async function handleBulkAdd() {
  await prepareEnrollment(csvHosts.value.map(hostPayload));
}

async function prepareEnrollment(hostsToEnroll) {
  enrollmentLoading.value = true;
  enrollmentFailures.value = [];
  try {
    pendingEnrollmentHosts.value = hostsToEnroll;
    enrollmentPreview.value = await previewHostEnrollment(hostsToEnroll);
  } catch (e) {
    window.$toast?.error("Couldn't inspect SSH enrollment", e);
  } finally {
    enrollmentLoading.value = false;
  }
}

function resetEnrollmentPreview() {
  enrollmentPreview.value = null;
  enrollmentFailures.value = [];
  pendingEnrollmentHosts.value = [];
}

function closeAddHost() {
  showAddHost.value = false;
  resetEnrollmentPreview();
}

function enrollmentStatusClass(host) {
  if (host.already_exists || host.trust_status === "trusted") return "badge-green";
  if (host.trust_status === "new") return "badge-orange";
  return "badge-red";
}

async function approveEnrollment() {
  enrollmentSubmitting.value = true;
  enrollmentFailures.value = [];
  try {
    const approvals = enrollmentPreview.value.hosts.map((host) => ({
      hostname: host.hostname,
      fingerprint: host.fingerprint,
    }));
    const result = await enrollHosts({
      hosts: pendingEnrollmentHosts.value,
      approvals,
    });
    enrollmentFailures.value = result.failed || [];
    if (enrollmentFailures.value.length) {
      window.$toast?.error(result.detail || "Some hosts could not be enrolled");
      return;
    }

    const added = result.added || [];
    showAddHost.value = false;
    resetEnrollmentPreview();
    newHost.value = emptyHost();
    csvHosts.value = [];
    csvErrors.value = [];
    window.$toast?.success(result.detail || `Enrolled ${added.length} host(s)`);
    await store.refresh({ force: true });
    if (added.length) showScanNudge(added);
  } catch (e) {
    window.$toast?.error("Couldn't enroll hosts", e);
  } finally {
    enrollmentSubmitting.value = false;
  }
}

onMounted(() => {
  store.start();
  loadOverview();
});
onUnmounted(() => store.stop());
</script>

<style scoped>
.fleet-hero {
  background: var(--surface-white);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  padding: var(--space-sm) var(--space-md);
  position: relative;
  overflow: hidden;
}

.fleet-hero::before {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(
    circle at top right,
    var(--surface-success-soft) 0%,
    transparent 60%
  );
  pointer-events: none;
}

.fleet-hero-grid {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) 2fr minmax(160px, 1fr);
  gap: var(--space-md);
  align-items: center;
  position: relative;
}

.fleet-headline-label {
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.7px;
  font-weight: 600;
}

.fleet-headline-value {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-family: var(--font-mono);
}

.fleet-headline-value span {
  font-size: 2.6rem;
  font-weight: 700;
  line-height: 1;
}

.fleet-headline-value small {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.fleet-headline-updated {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}

.fleet-hero-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fleet-bar-track {
  display: flex;
  height: 16px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--surface-lighter);
  border: 1px solid var(--border-subtle);
}

.fleet-bar-seg {
  height: 100%;
  transition: flex 0.5s ease;
}
.fleet-bar-online { background: var(--color-success); }
.fleet-bar-offline { background: var(--color-danger); }
.fleet-bar-unknown { background: var(--border-color); }
.fleet-bar-empty { flex: 1; background: var(--surface-lighter); }

.fleet-bar-legend {
  display: flex;
  gap: var(--space-sm);
  font-size: 12px;
  color: var(--text-secondary);
  flex-wrap: wrap;
}

.fleet-bar-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
}

.fleet-hero-jobs {
  text-align: right;
}

.fleet-jobs-value {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 6px;
  font-family: var(--font-mono);
}

.fleet-jobs-value > span {
  font-size: 2.6rem;
  font-weight: 700;
  line-height: 1;
}

.fleet-jobs-value .fleet-jobs-running {
  color: var(--color-info);
}

.fleet-jobs-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-info);
}

.quick-answers {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-sm);
  margin-top: var(--space-md);
}

.quick-card {
  min-height: 212px;
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  padding: var(--space-sm);
  background: var(--surface-white);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}

.quick-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-xs);
}

.quick-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.quick-value {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  margin-top: 3px;
  font-size: 22px;
  font-weight: 700;
  color: var(--text-on-light);
  line-height: 1.15;
}

.quick-value span {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.quick-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: var(--space-xs);
}

.quick-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-xs);
  min-height: 28px;
  padding: 5px 8px;
  background: var(--surface-light);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  font-size: 12px;
}

.quick-row span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quick-row strong {
  flex: 0 0 auto;
  font-family: var(--font-mono);
  font-size: 12px;
}

.quick-empty {
  margin: var(--space-xs) 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.4;
}

.quick-actions {
  display: flex;
  gap: var(--space-xs);
  align-items: center;
  margin-top: auto;
}

.quick-icon-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  text-decoration: none;
}

.quick-icon-link:hover {
  color: var(--text-on-light);
  background: var(--surface-lighter);
}

.csv-warnings {
  margin-top: var(--space-sm);
  padding: var(--space-xs) var(--space-sm);
  background: var(--surface-warning-soft);
  border: 1px solid var(--color-warning);
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.csv-warnings strong i { color: var(--color-warning); margin-right: 4px; }
.csv-warnings ul {
  margin: 4px 0 0 var(--space-sm);
  padding: 0;
  font-size: 12px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.auth-toggle {
  margin-bottom: var(--space-sm);
}

.form-help,
.enrollment-detail {
  display: block;
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.enrollment-table {
  max-height: 300px;
  margin-top: var(--space-sm);
  overflow-y: auto;
}

.enrollment-table code {
  font-size: 11px;
  overflow-wrap: anywhere;
}

@media (max-width: 900px) {
  .quick-answers {
    grid-template-columns: 1fr;
  }
  .fleet-hero-grid {
    grid-template-columns: 1fr;
    gap: var(--space-sm);
  }
  .fleet-hero-jobs {
    text-align: left;
  }
  .fleet-jobs-value {
    justify-content: flex-start;
  }
}
</style>
