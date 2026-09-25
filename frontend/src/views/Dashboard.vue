<template>
  <div class="overview">
    <header class="page-header overview-header">
      <div>
        <h1>Overview</h1>
        <p v-if="store.hasLoadedOnce" class="evidence-header">{{ devices.length }} {{ devices.length === 1 ? 'device' : 'devices' }} · View refreshed <time :datetime="store.lastUpdated" :title="formatLongTime(store.lastUpdated)">{{ relativeTime(store.lastUpdated) }}</time> · Device observation ages vary</p>
        <p v-else class="evidence-header">{{ store.deviceError ? 'Device count unknown' : 'Retrieving fleet observations…' }}</p>
      </div>
      <div class="header-actions">
        <button class="btn btn-ghost btn-sm" :disabled="store.loading" @click="refresh"><i :class="['fas', store.loading ? 'fa-spinner fa-spin' : 'fa-sync-alt']" aria-hidden="true"></i>{{ store.loading ? 'Refreshing…' : 'Refresh view' }}</button>
        <router-link to="/devices?add=1" class="btn btn-ghost btn-sm">Add device</router-link>
      </div>
    </header>
    <p class="visually-hidden" role="status" aria-live="polite">{{ announcement }}</p>
    <div v-if="store.deviceError" class="observation-notice" role="status">
      <strong>{{ store.hasLoadedOnce ? 'Device observations could not be refreshed' : 'Fleet state is unavailable' }}</strong>
      <p>{{ store.hasLoadedOnce ? `Showing the last successful view from ${formatLongTime(store.lastUpdated)}. Conditions may have changed.` : 'Device data could not be retrieved. No health assessment is available.' }}</p>
      <button class="btn btn-ghost btn-sm" :disabled="store.loading" @click="refresh">Retry</button>
    </div>
    <section v-if="!store.hasLoadedOnce && !store.deviceError" class="overview-panel loading-state" aria-busy="true" aria-label="Loading fleet observations"><i class="fas fa-spinner fa-spin" aria-hidden="true"></i>Loading devices and current work…</section>
    <section v-else-if="store.hasLoadedOnce && !devices.length && !store.deviceError" class="overview-panel onboarding">
      <span class="eyebrow">Getting started</span><h2>Connect your first device</h2>
      <p>Enroll a Linux device over SSH or a supported robot. Discovery determines which operations are available.</p>
      <ol><li><strong>Connect and verify identity.</strong><span>Review the endpoint and SSH fingerprint where supported.</span></li><li><strong>Inspect the first observation.</strong><span>Confirm device type, facts, and capabilities.</span></li><li><strong>Choose an inspection.</strong><span>Review its targets and results before planning maintenance.</span></li></ol>
      <div class="header-actions"><router-link class="btn btn-primary" to="/devices?add=1">Add first device</router-link><router-link class="btn btn-ghost" to="/devices?import=1">Import devices from CSV</router-link></div>
    </section>

    <template v-if="store.hasLoadedOnce && devices.length">
      <section class="condition-brief" :class="{ 'has-attention': affectedCount }" aria-labelledby="fleet-condition">
        <span class="eyebrow">{{ store.deviceError ? 'Last known conditions' : affectedCount ? 'Attention required' : 'Latest observations' }}</span>
        <h2 id="fleet-condition">{{ conditionTitle }}</h2>
        <p>{{ firstStep }}</p>
        <div class="reachability"><span>Last known reachability: <strong>{{ onlineCount }} online · {{ offlineCount }} offline · {{ devices.length - onlineCount - offlineCount }} unknown</strong></span><router-link to="/devices">View inventory</router-link></div>
      </section>
      <div class="overview-columns">
        <section ref="queueElement" class="overview-panel next-steps" aria-labelledby="next-steps-title">
          <header class="panel-heading"><div><h2 id="next-steps-title" tabindex="-1">Next steps</h2><p>{{ affectedCount ? `Ranked by consequence. Groups overlap across ${affectedCount} ${affectedCount === 1 ? 'device' : 'devices'}.` : 'No conditions flagged in the latest observations.' }}</p></div><router-link v-if="affectedCount" to="/devices?attention=1">All affected devices</router-link></header>
          <div v-if="pendingObservations" class="queue-update"><button class="btn btn-ghost btn-sm" @click="applyObservations">Update priorities with new observations</button><p>Your current view is held while you inspect this queue.</p></div>
          <AttentionGroup v-for="group in groups" :key="group.id" :group="group" :jobs="store.activeJobs" />
          <div v-if="!groups.length" class="panel-empty"><strong>No current device alerts</strong><p>This reflects the latest recorded facts, not continuous monitoring.</p><router-link :to="{ path: '/operations', query: { operation: 'system.scan' } }">Review a fresh scan</router-link></div>
        </section>
        <div class="work-column">
          <section class="overview-panel" aria-labelledby="work-title">
            <header class="panel-heading"><div><h2 id="work-title">Work in progress</h2><p>{{ activeSummary }}</p></div><router-link to="/activity?status=active">Activity</router-link></header>
            <p v-if="store.activeError" class="panel-notice">Work could not be refreshed. {{ store.activeUpdated ? `Last observation: ${formatLongTime(store.activeUpdated)}.` : 'Active work is unknown.' }}</p>
            <article v-for="job in store.activeJobs.slice(0, 4)" :key="job.job_id" class="work-item">
              <div class="work-item-head"><StatusBadge :status="job.status" /><h3>{{ operationLabel(job.playbook) }}</h3></div>
              <p class="job-targets" :title="job.target_devices">{{ formatTargetList(job.target_devices) }}<span v-if="job.phase && job.status !== 'pending'"> · {{ job.phase.replaceAll('_', ' ') }}</span></p>
              <p><time :datetime="job.started_at || job.created_at" :title="formatLongTime(job.started_at || job.created_at)">{{ job.started_at ? 'Started' : 'Queued' }} {{ relativeTime(job.started_at || job.created_at) }}</time></p>
              <router-link :to="{ path: '/activity', query: { job: job.job_id } }">{{ job.status === 'pending' ? 'Review queued job' : 'Open job output' }}</router-link>
            </article>
            <p v-if="store.activeJobCount === 0 && !store.activeError" class="panel-empty">No active jobs.</p>
            <p v-if="store.activeJobCount > 4" class="panel-footer"><router-link to="/activity?status=active">View all {{ store.activeJobCount }} active jobs</router-link></p>
          </section>
          <section class="overview-panel" aria-labelledby="outcomes-title">
            <header class="panel-heading"><div><h2 id="outcomes-title">Recent outcomes</h2><p v-if="store.jobsUpdated">{{ outcomes.total }} completed in the latest {{ store.recentJobs.length }} loaded jobs</p></div></header>
            <p v-if="store.jobsError" class="panel-notice">Recent outcomes could not be refreshed. {{ store.jobsUpdated ? `Last observation: ${formatLongTime(store.jobsUpdated)}.` : 'Outcomes are unknown.' }}</p>
            <div v-if="store.jobsUpdated" class="outcome-summary">
              <div class="outcome-counts"><router-link to="/activity?status=success">{{ outcomes.counts.success }} succeeded</router-link><router-link to="/activity?status=failed">{{ outcomes.counts.failed }} failed</router-link><router-link to="/activity?status=recovery_required">{{ outcomes.counts.recovery_required }} recovery</router-link><router-link v-if="outcomes.counts.cancelled" to="/activity?status=cancelled">{{ outcomes.counts.cancelled }} cancelled</router-link></div>
              <p>A sample of jobs, not a time-window success rate.</p>
            </div>
            <div class="adverse-heading"><h3>Latest adverse outcomes</h3><p>Historical results may already be addressed.</p></div>
            <p v-if="store.adverseError" class="panel-notice">Adverse outcomes could not be refreshed. {{ store.adverseUpdated ? `Last observation: ${formatLongTime(store.adverseUpdated)}.` : 'History is unavailable.' }}</p>
            <router-link v-for="job in store.adverseJobs.slice(0, 3)" :key="job.job_id" :to="{ path: '/activity', query: { job: job.job_id } }" class="adverse-item">
              <span :class="['condition-tag', 'danger']">{{ job.status === 'recovery_required' ? 'Recovery required' : 'Failed' }}</span><strong>{{ operationLabel(job.playbook) }}</strong><span>{{ formatTargetList(job.target_devices) }}</span><time :datetime="job.finished_at || job.created_at" :title="formatLongTime(job.finished_at || job.created_at)">{{ relativeTime(job.finished_at || job.created_at) }}</time>
            </router-link>
            <p v-if="store.adverseUpdated && !store.adverseJobs.length && !store.adverseError" class="panel-empty">No failed or recovery-required jobs found.</p>
            <p class="panel-footer"><router-link to="/activity?status=adverse">Review adverse outcomes</router-link></p>
          </section>
        </div>
      </div>
      <div class="overview-secondary">
        <section class="overview-panel secondary-panel"><h2>Observation coverage</h2><p>Root storage: <strong>{{ coverage.reported }} reported</strong> · {{ coverage.missing }} unreported · {{ coverage.stale }} stale or undated</p><p v-if="coverage.worst !== null">Worst recorded root storage: <strong>{{ coverage.worst }}%</strong></p><p>Missing readings stay unknown. Open device evidence for observation timestamps.</p><router-link to="/devices?reason=verification">Review stale or missing facts</router-link></section>
        <section class="overview-panel secondary-panel"><h2>Fleet composition</h2><p><router-link v-if="coverage.gpu" to="/devices?capability=gpu.inspect">{{ coverage.gpu }} GPU capable</router-link><span v-else>0 GPU capable</span> · {{ coverage.other }} other devices · <router-link v-if="coverage.robots" to="/devices?kind=robot">{{ coverage.robots }} robots</router-link><span v-else>0 robots</span></p><p>Capabilities describe supported operations. They do not imply utilization or maintenance readiness.</p><router-link to="/operations">Review operation eligibility</router-link></section>
      </div>
    </template>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue';
import { useDevicesStore } from '../stores/devices.js';
import AttentionGroup from '../components/AttentionGroup.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { attentionGroups, completedSummary, fleetCoverage } from '../utils/fleetOverview.js';
import { formatTargetList, operationLabel } from '../utils/devices.js';
import { relativeTime, formatLongTime } from '../utils/time.js';
const store = useDevicesStore();
const devices = computed(() => store.devices);
const queueElement = ref(null), queueDevices = ref(store.devices), pendingObservations = ref(false), announcement = ref('');
watch(() => store.devices, rows => {
  if (JSON.stringify(rows) === JSON.stringify(queueDevices.value)) { pendingObservations.value = false; return; }
  if (queueElement.value?.contains(document.activeElement)) { pendingObservations.value = true; return; }
  queueDevices.value = rows;
  pendingObservations.value = false;
});
function applyObservations() { queueDevices.value = store.devices; pendingObservations.value = false; queueElement.value?.querySelector('h2')?.focus(); }
const groups = computed(() => attentionGroups(queueDevices.value));
const affectedCount = computed(() => new Set(groups.value.flatMap(group => group.devices.map(device => device.id))).size);
const onlineCount = computed(() => devices.value.filter(device => device.status === 'online').length);
const offlineCount = computed(() => devices.value.filter(device => device.status === 'offline').length);
const coverage = computed(() => fleetCoverage(devices.value));
const outcomes = computed(() => completedSummary(store.recentJobs));
const conditionTitle = computed(() => offlineCount.value === devices.value.length ? 'No devices currently reported reachable' : affectedCount.value ? `${affectedCount.value} ${affectedCount.value === 1 ? 'device needs' : 'devices need'} attention` : 'No current device alerts');
const firstStep = computed(() => {
  const group = groups.value[0];
  if (!group) return 'Review observation age before planning maintenance.';
  return `${group.title}: ${group.devices.slice(0, 2).map(device => device.name).join(', ')}${group.devices.length > 2 ? ` and ${group.devices.length - 2} more` : ''}.`;
});
const activeSummary = computed(() => store.activeJobCount == null ? (store.activeError ? 'Work state unavailable' : 'Loading work…') : `${store.activeJobCount} active${store.activeJobCount > store.activeJobs.length ? ` · ${store.activeJobs.length} loaded` : ''}`);
async function refresh() { await store.refresh(); applyObservations(); announcement.value = store.error ? 'Some observations could not be refreshed.' : 'Fleet view refreshed.'; }
</script>
<style scoped>
.overview { font-size: 14px; }.overview h1 { font-size: 28px; letter-spacing: -.5px; }.overview-header { margin-bottom: 22px; }.evidence-header { color: var(--text-secondary); font-size: 12px; margin-top: 8px; }.header-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.overview-panel, .condition-brief { border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--surface-white); min-width: 0; overflow: hidden; }.condition-brief { padding: 16px 20px; margin-bottom: 20px; border-left: 4px solid var(--border-color); }.condition-brief.has-attention { border-left-color: var(--status-danger-text); }.condition-brief h2 { margin: 6px 0; font-size: 22px; letter-spacing: -.3px; }.eyebrow { font-size: 11px; text-transform: uppercase; letter-spacing: .6px; font-weight: 700; color: var(--text-secondary); }.has-attention .eyebrow { color: var(--status-danger-text); }.reachability { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; border-top: 1px solid var(--border-subtle); padding-top: 10px; margin-top: 14px; font-size: 12px; color: var(--text-secondary); }
.overview-columns { display: grid; grid-template-columns: minmax(0,1.65fr) minmax(290px,1fr); gap: 20px; align-items: start; }.work-column { display: grid; gap: 20px; min-width: 0; }.panel-heading { padding: 16px 20px; display: flex; align-items: start; justify-content: space-between; gap: 12px; }.panel-heading h2 { font-size: 18px; }.panel-heading p { font-size: 12px; color: var(--text-secondary); margin-top: 5px; }.panel-heading > a { font-size: 12px; flex-shrink: 0; }.panel-empty { padding: 20px; color: var(--text-secondary); }.panel-empty p { margin: 6px 0; }.panel-footer { padding: 12px 20px; border-top: 1px solid var(--border-subtle); font-size: 13px; }
.work-item { padding: 10px 20px; border-top: 1px solid var(--border-subtle); }.work-item-head { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }.work-item h3 { font-size: 14px; margin: 0; }.work-item p { font-size: 12px; color: var(--text-secondary); margin: 3px 0; }.job-targets { overflow-wrap: anywhere; }.work-item a { display: inline-block; margin-top: 5px; font-size: 13px; }.job-phase { font-size: 12px; color: var(--text-secondary); margin-left: 8px; }.outcome-summary { padding: 0 20px 16px; }.outcome-counts { display: flex; flex-wrap: wrap; gap: 8px 16px; font-weight: 650; }.outcome-summary p, .adverse-heading p { font-size: 12px; color: var(--text-secondary); margin-top: 6px; }.adverse-heading { padding: 12px 20px; border-top: 1px solid var(--border-subtle); }.adverse-heading h3 { font-size: 14px; }.adverse-item { padding: 12px 20px; display: grid; grid-template-columns: 1fr auto; gap: 4px 12px; border-top: 1px solid var(--border-subtle); color: var(--text-primary); font-size: 13px; }.adverse-item .condition-tag { grid-column: 1/-1; width: fit-content; }.adverse-item strong { grid-column: 1/-1; }.adverse-item > span:not(.condition-tag), .adverse-item time { color: var(--text-secondary); font-size: 12px; overflow-wrap: anywhere; }.adverse-item:hover { background: var(--surface-light); }
.overview-secondary { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }.secondary-panel { padding: 16px 20px; }.secondary-panel h2 { font-size: 16px; }.secondary-panel p { color: var(--text-secondary); font-size: 13px; margin: 8px 0; }.secondary-panel a { font-size: 13px; }.observation-notice, .panel-notice { background: var(--surface-warning-soft); color: var(--text-primary); padding: 14px 20px; font-size: 13px; }.observation-notice { border-left: 4px solid var(--status-warning-text); margin-bottom: 20px; }.observation-notice p { margin: 5px 0 10px; }.queue-update { padding: 12px 20px; background: var(--surface-info-soft); }.queue-update p { font-size: 12px; margin-top: 5px; }.loading-state { padding: 48px 24px; color: var(--text-secondary); }.loading-state i { margin-right: 8px; }.onboarding { padding: 32px; }.onboarding h2 { font-size: 24px; margin: 8px 0 12px; }.onboarding > p { max-width: 62ch; color: var(--text-secondary); }.onboarding ol { padding-left: 22px; margin: 22px 0; }.onboarding li { padding: 8px 0; }.onboarding li span { display: block; color: var(--text-secondary); font-size: 13px; }
@media (max-width: 900px) { .overview-columns { grid-template-columns: 1fr; }.work-column { grid-template-columns: 1fr 1fr; }.overview-header { align-items: start; } }
@media (max-width: 620px) { .overview-header { flex-direction: column; gap: 14px; }.overview-secondary, .work-column { grid-template-columns: 1fr; }.panel-heading { flex-wrap: wrap; padding: 16px; }.condition-brief { padding: 16px; }.onboarding { padding: 24px 16px; }.adverse-item { grid-template-columns: 1fr; } }
</style>
