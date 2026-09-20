<template>
  <div>
    <div class="page-header">
      <div>
        <h2>Fleet overview</h2>
        <p class="page-subtitle">Availability, attention, and active work across every managed device.</p>
      </div>
      <div class="flex gap-xs">
        <button class="btn btn-ghost btn-sm" :disabled="store.loading" @click="refresh">
          <i :class="['fas', store.loading ? 'fa-spinner fa-spin' : 'fa-sync-alt']" aria-hidden="true"></i>
          {{ store.loading ? 'Refreshing…' : 'Refresh' }}
        </button>
        <button class="btn btn-primary btn-sm" @click="scanAll">
          <i class="fas fa-satellite-dish" aria-hidden="true"></i> Scan fleet
        </button>
        <router-link to="/devices?add=1" class="btn btn-primary btn-sm">
          <i class="fas fa-plus" aria-hidden="true"></i> Add device
        </router-link>
      </div>
    </div>

    <section class="overview-hero" aria-labelledby="fleet-health-heading">
      <div>
        <span class="eyebrow">Fleet</span>
        <h3 id="fleet-health-heading">{{ healthMessage }}</h3>
        <p>{{ devices.length }} device{{ devices.length === 1 ? '' : 's' }} across {{ kindCount }} type{{ kindCount === 1 ? '' : 's' }}</p>
      </div>
      <div class="health-bar" :aria-label="`${online.length} online, ${offline.length} offline, ${unknown.length} unknown`">
        <span v-if="online.length" class="health-online" :style="{ flex: online.length }"></span>
        <span v-if="offline.length" class="health-offline" :style="{ flex: offline.length }"></span>
        <span v-if="unknown.length || !devices.length" class="health-unknown" :style="{ flex: unknown.length || 1 }"></span>
      </div>
      <div class="health-legend">
        <span><i class="dot dot-green"></i>{{ online.length }} online</span>
        <span><i class="dot dot-red"></i>{{ offline.length }} offline</span>
        <span><i class="dot dot-gray"></i>{{ unknown.length }} unknown</span>
      </div>
    </section>

    <section class="metric-grid" aria-label="Fleet summary">
      <router-link to="/devices" class="metric-card">
        <i class="fas fa-server metric-icon" aria-hidden="true"></i>
        <div><strong>{{ devices.length }}</strong><span>Devices</span></div>
      </router-link>
      <router-link to="/activity" class="metric-card">
        <i class="fas fa-bolt metric-icon" aria-hidden="true"></i>
        <div><strong>{{ store.activeJobCount ?? "--" }}</strong><span>Active jobs</span></div>
      </router-link>
      <router-link to="/devices?attention=1" class="metric-card" :class="{ warning: attentionCount }">
        <i class="fas fa-triangle-exclamation metric-icon" aria-hidden="true"></i>
        <div><strong>{{ attentionCount }}</strong><span>Need attention</span></div>
      </router-link>
      <router-link v-if="gpuDevices.length" to="/devices?capability=gpu.inspect" class="metric-card">
        <i class="fas fa-microchip metric-icon" aria-hidden="true"></i>
        <div><strong>{{ gpuDevices.length }}</strong><span>GPU devices</span></div>
      </router-link>
      <router-link v-if="robotDevices.length" to="/devices?kind=robot" class="metric-card">
        <i class="fas fa-robot metric-icon" aria-hidden="true"></i>
        <div><strong>{{ robotDevices.length }}</strong><span>Robots</span></div>
      </router-link>
    </section>

    <div class="content-grid">
      <section class="card">
        <div class="card-body">
          <div class="section-header">
            <div><span class="eyebrow">Priorities</span><h3>Needs attention</h3></div>
            <router-link to="/devices?attention=1">View devices</router-link>
          </div>
          <div v-if="attentionItems.length" class="attention-list">
            <router-link v-for="item in attentionItems.slice(0, 7)" :key="`${item.device.id}-${item.reason}`" :to="`/devices/${item.device.id}`" class="attention-row">
              <span :class="['status-symbol', item.severity]" aria-hidden="true"><i :class="['fas', item.icon]"></i></span>
              <span><strong>{{ item.device.name }}</strong><small>{{ item.reason }}</small></span>
              <i class="fas fa-chevron-right" aria-hidden="true"></i>
            </router-link>
          </div>
          <div v-else class="empty-compact"><i class="fas fa-circle-check" aria-hidden="true"></i>No current device alerts.</div>
        </div>
      </section>

      <section class="card">
        <div class="card-body">
          <div class="section-header">
            <div><span class="eyebrow">Recent</span><h3>Activity</h3></div>
            <router-link to="/activity">View all</router-link>
          </div>
          <div v-if="recentJobs.length" class="activity-list">
            <router-link v-for="job in recentJobs.slice(0, 6)" :key="job.job_id" :to="`/activity?job=${job.job_id}`" class="activity-row">
              <StatusBadge :status="job.status" />
              <span><strong>{{ operationLabel(job.playbook) }}</strong><small>{{ formatTargetList(job.target_devices) }}</small></span>
              <time>{{ relativeTime(job.created_at) }}</time>
            </router-link>
          </div>
          <div v-else class="empty-compact">No operations have run yet.</div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from "vue";
import { scanAllDevices } from "../api.js";
import { useDevicesStore } from "../stores/devices.js";
import StatusBadge from "../components/StatusBadge.vue";
import { hasCapability, formatTargetList, operationLabel } from "../utils/devices.js";
import { relativeTime } from "../utils/time.js";

const store = useDevicesStore();
const devices = computed(() => store.devices);
const recentJobs = computed(() => store.recentJobs);
const online = computed(() => devices.value.filter((device) => device.status === "online"));
const offline = computed(() => devices.value.filter((device) => device.status === "offline"));
const unknown = computed(() => devices.value.filter((device) => !["online", "offline"].includes(device.status)));
const kindCount = computed(() => new Set(devices.value.map((device) => device.kind)).size);
const gpuDevices = computed(() => devices.value.filter((device) => hasCapability(device, "gpu.inspect")));
const robotDevices = computed(() => devices.value.filter((device) => device.kind === "robot"));
const healthMessage = computed(() => {
  if (!devices.value.length) return "Build your mixed fleet";
  if (offline.value.length) return `${offline.value.length} device${offline.value.length === 1 ? '' : 's'} offline`;
  if (unknown.value.length) return `${unknown.value.length} device${unknown.value.length === 1 ? '' : 's'} need a scan`;
  return "All devices are reachable";
});
const attentionItems = computed(() => {
  const items = [];
  devices.value.forEach((device) => {
    if (device.recovery_required) items.push({ device, reason: "Recovery verification required", severity: "danger", icon: "fa-triangle-exclamation" });
    else if (device.facts_stale) items.push({ device, reason: "Facts need verification", severity: "warning", icon: "fa-satellite-dish" });
    if (device.status === "offline") items.push({ device, reason: "Device is offline", severity: "danger", icon: "fa-link-slash" });
    else if (device.status === "unknown") items.push({ device, reason: "No successful scan yet", severity: "muted", icon: "fa-circle-question" });
    if (device.reboot_required) items.push({ device, reason: "Reboot required", severity: "warning", icon: "fa-power-off" });
    if ((device.disk_root_percent || 0) >= 85) items.push({ device, reason: `Root storage is ${device.disk_root_percent}% full`, severity: "warning", icon: "fa-hard-drive" });
  });
  return items;
});
const attentionCount = computed(() => new Set(attentionItems.value.map((item) => item.device.id)).size);

async function refresh() { await store.refresh({ force: true }); }
async function scanAll() {
  try { await scanAllDevices(); window.$toast?.success("Fleet scan started"); }
  catch (error) { window.$toast?.error("Couldn't start fleet scan", error); }
}
onMounted(() => store.start());
onUnmounted(() => store.stop());
</script>

<style scoped>
.page-subtitle { margin: 4px 0 0; color: var(--text-secondary); }
.overview-hero { padding: 24px 28px; border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); background: linear-gradient(135deg, var(--surface-white), var(--surface-light)); box-shadow: var(--shadow-card); }
.overview-hero h3 { margin: 4px 0; font-size: 26px; }.overview-hero p { margin: 0; color: var(--text-secondary); }
.eyebrow { color: var(--text-secondary); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .8px; }
.health-bar { display: flex; height: 9px; margin-top: 22px; border-radius: 8px; overflow: hidden; background: var(--surface-lighter); }.health-online { background: var(--color-success); }.health-offline { background: var(--color-danger); }.health-unknown { background: var(--border-color); }
.health-legend { display: flex; gap: 18px; margin-top: 10px; font-size: 12px; color: var(--text-secondary); }.health-legend span { display: flex; align-items: center; gap: 6px; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: 12px; margin: 18px 0; }
.metric-card { display: flex; align-items: center; gap: 14px; padding: 16px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--surface-white); color: var(--text-primary); text-decoration: none; box-shadow: var(--shadow-card); }.metric-card:hover { border-color: var(--color-accent); text-decoration: none; }.metric-card.warning .metric-icon { color: var(--color-warning); }
.metric-icon { width: 34px; color: var(--color-accent); font-size: 20px; text-align: center; }.metric-card div { display: flex; flex-direction: column; }.metric-card strong { font-size: 24px; line-height: 1; }.metric-card span { color: var(--text-secondary); font-size: 12px; margin-top: 5px; }
.content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }.section-header h3 { margin: 2px 0 0; }
.attention-list, .activity-list { display: flex; flex-direction: column; }.attention-row, .activity-row { display: grid; align-items: center; gap: 12px; padding: 11px 4px; border-top: 1px solid var(--border-subtle); color: inherit; text-decoration: none; }.attention-row { grid-template-columns: auto 1fr auto; }.activity-row { grid-template-columns: auto 1fr auto; }.attention-row:hover, .activity-row:hover { text-decoration: none; background: var(--surface-light); }.attention-row span:nth-child(2), .activity-row span:nth-child(2) { display: flex; flex-direction: column; }.attention-row small, .activity-row small, .activity-row time { color: var(--text-secondary); font-size: 11px; }
.status-symbol { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; }.status-symbol.danger { background: var(--surface-danger-soft); color: var(--color-danger); }.status-symbol.warning { background: var(--surface-warning-soft); color: var(--color-warning); }.status-symbol.muted { background: var(--surface-lighter); color: var(--text-secondary); }
.empty-compact { padding: 30px 8px; color: var(--text-secondary); display: flex; align-items: center; justify-content: center; gap: 8px; }
@media (max-width: 780px) { .content-grid { grid-template-columns: 1fr; }.page-header { align-items: flex-start; }.page-header > .flex { flex-wrap: wrap; justify-content: flex-end; } }
</style>
