<template>
  <div>
    <div class="page-header">
      <h2>Activity</h2>
      <div class="flex gap-xs">
        <label class="visually-hidden" for="job-filter-status">Filter by status</label>
        <select id="job-filter-status" v-model="filterStatus" class="form-select" style="width: auto; min-width: 140px">
          <option value="">All statuses</option><option value="active">Active work</option><option value="adverse">Adverse outcomes</option>
          <option value="success">Success</option>
          <option value="partial">Partial</option>
          <option value="failed">Failed</option>
          <option value="running">Running</option>
          <option value="pending">Pending</option>
          <option value="cancelled">Cancelled</option><option value="cancelling">Cancelling</option><option value="recovery_required">Health check pending</option>
        </select>
        <button class="btn btn-ghost btn-sm" aria-label="Refresh job list" @click="load">
          <i class="fas fa-sync-alt" aria-hidden="true"></i> Refresh
        </button>
      </div>
    </div>

    <div class="activity-filters"><label>Operation<select v-model="filterPlaybook" class="form-select"><option value="">All operations</option><option v-for="playbook in operationOptions" :key="playbook" :value="playbook">{{ operationLabel(playbook) }}</option></select></label><label>Device in loaded jobs<input v-model="filterTarget" type="search" class="form-input" placeholder="Inventory name" /></label><label>Created within<select v-model="filterPeriod" class="form-select"><option value="">Any time</option><option value="24h">24 hours</option><option value="7d">7 days</option></select></label></div>
    <p class="activity-coverage">{{ loading ? 'Refreshing activity…' : `Page ${page + 1}: ${visibleJobs.length} visible jobs` }}. <span v-if="filterStatus === 'adverse'">Each page loads up to 50 jobs per adverse status. </span>Device and time filters apply to this loaded page. <router-link to="/">Back to Overview</router-link></p>
    <p v-if="loadError" class="callout callout-warn" role="status">Activity could not be refreshed. {{ jobs.length ? 'Showing the last loaded jobs.' : 'Job history is unavailable.' }}</p>
    <p v-if="detailError" class="callout callout-danger" role="alert">The selected job could not be loaded. <button class="btn btn-ghost btn-sm" @click="showJob(route.query.job)">Retry job</button></p>
    <div v-if="visibleJobs.length" class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Operation</th>
            <th>Devices</th>
            <th>Status</th>
            <th>Duration</th>
            <th>Triggered By</th>
            <th>When</th>
            <th aria-label="Expand"></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="job in visibleJobs" :key="job.job_id">
            <tr style="cursor: pointer" @click="toggleExpand(job.job_id)">
              <td><strong>{{ operationLabel(job.playbook) }}</strong></td>
              <td>{{ formatTargetList(job.target_devices) }}</td>
              <td><StatusBadge :status="job.status" /></td>
              <td>{{ job.duration_seconds ? job.duration_seconds + 's' : '--' }}</td>
              <td>{{ job.triggered_by }}</td>
              <td>{{ formatTime(job.created_at) }}</td>
              <td>
                <button type="button" class="btn btn-ghost btn-sm btn-icon" :aria-label="`${expanded === job.job_id ? 'Collapse' : 'Expand'} ${operationLabel(job.playbook)} details`" :aria-expanded="expanded === job.job_id" @click.stop="toggleExpand(job.job_id)"><i
                  :class="['fas', expanded === job.job_id ? 'fa-chevron-up' : 'fa-chevron-down']"
                  :aria-label="expanded === job.job_id ? 'Collapse details' : 'Expand details'"
                  style="color: var(--text-secondary)"
                aria-hidden="true"></i></button>
              </td>
            </tr>
            <tr v-if="job.recap && job.playbook !== 'storage_analysis.yml' && expanded !== job.job_id" style="cursor: pointer" @click="toggleExpand(job.job_id)">
              <td colspan="7" style="padding: 0">
                <div class="job-recap"><pre>{{ job.recap }}</pre></div>
              </td>
            </tr>
            <tr v-if="expanded === job.job_id">
              <td colspan="7" style="padding: 0">
                <div class="job-detail">
                  <p v-if="expandedJob?.error_summary" role="status" class="callout callout-danger">{{ expandedJob.error_summary }}</p>
                  <p v-if="expandedJob?.status === 'partial'" class="callout callout-warn">Some, but not all, devices completed successfully. Review the per-device outcomes and log below.</p>
                  <p v-if="expandedJob?.status === 'recovery_required'" class="callout callout-warn">This change did not finish with a confirmed result. The next install or cleanup checks device health automatically and continues if the check passes. Review device errors below and return to <router-link :to="{ path: '/operations', query: { targets: expandedJob.target_devices } }">Operations</router-link> when ready.</p>
                  <p v-if="expandedJob && ['pending', 'running', 'cancelling'].includes(expandedJob.status)">Phase: {{ expandedJob.phase?.replaceAll('_', ' ') }}. <button v-if="canCancel(expandedJob)" class="btn btn-ghost btn-sm" :disabled="cancelling" @click="requestCancel(expandedJob)">Cancel {{ expandedJob.status === 'pending' ? 'queued job' : 'inspection' }}</button><span v-else>Running changes finish under supervision; they cannot be safely cancelled.</span></p>
                  <ul v-if="visibleStorageOutcomes(expandedJob).length" class="outcomes" aria-label="Per-device outcomes"><li v-for="result in visibleStorageOutcomes(expandedJob)" :key="result.hostname"><strong>{{ result.hostname }}</strong>: {{ result.status.replaceAll('_', ' ') }}<p v-if="result.detail">{{ result.detail }}</p><p v-if="result.recovery_resolution">{{ result.recovery_resolution }}</p></li></ul>
                  <router-link v-if="expandedJob?.playbook === 'package_preview.yml' && expandedJob.status === 'success'" :to="`/operations?preview=${expandedJob.job_id}`" class="btn btn-primary btn-sm">Review and apply this preview</router-link>
                  <div v-if="job.recap && job.playbook !== 'storage_analysis.yml'" class="job-recap-expanded"><pre>{{ job.recap }}</pre></div>
                  <StorageResults :reports="expandedJob?.result_artifacts || []" />
                  <section v-if="expandedJob?.result_artifacts?.some(result => !['execution','storage'].includes(result.report_type))" class="result-grid" aria-label="Structured operation results">
                    <article v-for="result in expandedJob.result_artifacts.filter(item => !['execution','storage'].includes(item.report_type))" :key="`${result.report_type}-${result.hostname}`" class="result-card">
                      <div class="result-heading">
                        <span>{{ resultTitle(result.report_type) }}</span>
                        <strong>{{ result.hostname }}</strong>
                      </div>
                      <template v-if="result.report_type === 'packages'"><PackageResults :reports="[result]" /></template>
                      <template v-else-if="result.report_type === 'apt_install'"><p>{{ result.package_count }} packages installed. {{ result.reboot_required ? 'Reboot required; schedule it separately.' : 'No reboot required.' }}</p></template>
                      <template v-else-if="result.report_type === 'cleanup'"><p>{{ result.summary }}</p><details v-for="step in result.steps" :key="step.label"><summary>{{ step.label }} · {{ step.status }}</summary><pre class="structured-text">{{ step.output || 'Nothing to remove.' }}</pre></details></template>
                      <template v-else-if="result.report_type === 'kubernetes'"><dl><dt>Phase</dt><dd>{{ result.phase }}</dd><dt>Node</dt><dd>{{ result.node }}</dd><dt>Context</dt><dd>{{ result.context }}</dd><dt>Originally cordoned</dt><dd>{{ result.originally_unschedulable ? 'Yes' : 'No' }}</dd></dl></template>
                      <template v-else-if="result.report_type === 'services'"><p>{{ result.action === 'status' ? 'Observed services' : `${result.action}: ${result.service}` }}</p><details :open="result.action !== 'status'"><summary>Service states</summary><div class="service-results"><table><thead><tr><th>Unit</th><th>State</th><th>Startup</th></tr></thead><tbody><tr v-for="unit in Object.values(result.services || {}).sort((a,b) => a.name.localeCompare(b.name))" :key="unit.name"><td>{{ unit.name }}</td><td>{{ unit.state }}</td><td>{{ unit.status }}</td></tr></tbody></table></div></details></template>
                      <template v-else-if="result.report_type === 'accounts'"><p>{{ result.accounts?.length || 0 }} historical account observations.</p><ul><li v-for="account in result.accounts" :key="account.username">{{ account.username }}: {{ account.present ? 'present' : 'absent' }}</li></ul></template>
                      <template v-else-if="result.report_type === 'assessment'">
                        <div class="result-metrics">
                          <span class="metric-good"><strong>{{ result.summary?.pass_count || 0 }}</strong> passed</span>
                          <span class="metric-warn"><strong>{{ result.summary?.warning_count || 0 }}</strong> warnings</span>
                          <span class="metric-bad"><strong>{{ result.summary?.blocker_count || 0 }}</strong> blockers</span>
                        </div>
                      </template>
                      <template v-else-if="result.report_type === 'gpu'"><InspectionResults :reports="[result]" /></template>
                      <template v-else-if="result.report_type === 'driver'">
                        <div class="driver-change"><code>{{ result.pre_driver_version || 'unknown' }}</code><i class="fas fa-arrow-right" aria-hidden="true"></i><code>{{ result.post_driver_version || 'unknown' }}</code></div>
                        <p>{{ result.reboot_performed ? 'Reboot completed' : 'No reboot performed' }}</p>
                      </template>
                    </article>
                  </section>
                  <div v-if="job.extra_vars" class="job-vars">
                    <strong>Parameters:</strong> {{ job.extra_vars }}
                  </div>

                  <!-- Storage has a compact result above; keep its technical output expandable. -->
                  <component :is="expandedJob?.playbook === 'storage_analysis.yml' ? 'details' : 'div'" class="technical-output">
                    <summary v-if="expandedJob?.playbook === 'storage_analysis.yml'">Technical log</summary>
                    <div class="log-toolbar">
                      <strong>
                        Output
                        <span v-if="streaming" class="badge badge-blue" style="margin-left: 8px">
                          <span class="dot dot-blue dot-pulse" aria-hidden="true"></span> Live
                        </span>
                      </strong>
                      <div class="log-toolbar-right">
                        <button type="button" class="btn btn-ghost btn-sm" @click="askAboutJob(job)">
                          Ask Fleet Help
                        </button>
                        <button
                          type="button"
                          :class="['log-toggle', { active: autoScroll }]"
                          :aria-pressed="autoScroll"
                          @click="toggleAutoScroll"
                        >
                          Auto-scroll
                        </button>
                        <button
                          type="button"
                          :class="['log-toggle', { active: wrapLines }]"
                          :aria-pressed="wrapLines"
                          @click="wrapLines = !wrapLines"
                        >
                          Wrap
                        </button>
                      </div>
                    </div>
                    <div
                      ref="logContainers"
                      class="log-output"
                      :style="{ whiteSpace: wrapLines ? 'pre-wrap' : 'pre' }"
                      tabindex="0"
                      @scroll="onLogScroll"
                      v-html="renderedLog || '<span style=\'opacity:.5\'>No output available</span>'"
                    ></div>
                  </component>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <div v-else-if="!loading && !loadError" class="empty-state">
      <i class="fas fa-list-check" aria-hidden="true"></i>
      <p>No activity found</p>
      <router-link to="/" class="btn btn-primary btn-sm" style="display: inline-flex; margin-top: var(--space-sm)">
        <i class="fas fa-home" aria-hidden="true"></i> Back to overview
      </router-link>
    </div>
    <nav class="activity-pagination" aria-label="Activity pages"><button class="btn btn-ghost btn-sm" :disabled="page === 0 || loading" @click="setPage(page - 1)">Previous</button><span>Page {{ page + 1 }}</span><button class="btn btn-ghost btn-sm" :disabled="!hasNextPage || loading" @click="setPage(page + 1)">Next</button></nav>
  </div>
</template>

<script setup>
import StorageResults from "../components/StorageResults.vue";
import {visibleStorageOutcomes} from "../utils/storage.js";
import InspectionResults from "../components/InspectionResults.vue";
import PackageResults from "../components/PackageResults.vue";
import { ref, watch, onMounted, onUnmounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import AnsiToHtml from "ansi-to-html";
import { getJobs, getJob, streamJobOutput, cancelJob } from "../api.js";
import StatusBadge from "../components/StatusBadge.vue";
import { formatTargetList, operationLabel, OPERATION_LABELS } from "../utils/devices.js";
import { targetNames } from "../utils/fleetOverview.js";
import { formatLongTime, ageInMs } from "../utils/time.js";

const jobs = ref([]);
const cancelling = ref(false);
let refreshTimer; let disposed = false;
function canCancel(job) { return !job.playbook.startsWith("reachy.") && (job.status === "pending" || (job.status === "running" && job.execution_kind === "read_only")); }
async function requestCancel(job) { cancelling.value = true; try { await cancelJob(job.job_id); expandedJob.value = await getJob(job.job_id); await load(); } catch(e) { window.$toast?.error("Could not cancel job", e); } finally { cancelling.value = false; } }
const route = useRoute();
const router = useRouter();
const loading = ref(true), loadError = ref(null), detailError = ref(null), hasNextPage = ref(false);
let loadSequence = 0;
function routeFilter(key) { return computed({ get: () => String(route.query[key] || ''), set: value => router.replace({ query: { ...route.query, [key]: value || undefined, page: undefined, job: undefined } }) }); }
const filterStatus = routeFilter('status'), filterPlaybook = routeFilter('playbook'), filterTarget = routeFilter('target'), filterPeriod = routeFilter('period');
const page = computed(() => Math.max(0, Math.min(100000, Number.parseInt(route.query.page, 10) || 0)));
function setPage(value) { router.replace({ query: { ...route.query, page: value || undefined, job: undefined } }); }
const operationOptions = computed(() => [...new Set([...Object.keys(OPERATION_LABELS), ...jobs.value.map(job => job.playbook), filterPlaybook.value].filter(Boolean))].sort((a,b) => operationLabel(a).localeCompare(operationLabel(b))));
const visibleJobs = computed(() => jobs.value.filter(job => {
  if (job.job_id === expanded.value) return true;
  const target = !filterTarget.value || targetNames(job).some(name => name.toLowerCase().includes(filterTarget.value.toLowerCase()));
  const windowMs = ({ '24h': 86400000, '7d': 604800000 })[filterPeriod.value];
  const age = ageInMs(job.created_at);
  return target && (!windowMs || (age !== null && age >= 0 && age <= windowMs));
}));
const expanded = ref(null);
const expandedJob = ref(null);
const liveOutput = ref("");
const streaming = ref(false);
// Template refs inside v-for are arrays, even with only one expanded job.
const logContainers = ref([]);
const logContainer = computed(() => logContainers.value[0]);

const autoScroll = ref(true);
const wrapLines = ref(true);
let autoScrollDisabled = false;
let lastScrollTop = 0;

let streamController = null;
const ansiConverter = new AnsiToHtml({
  fg: "#d8e4c5",
  bg: "#0b0b0b",
  newline: false,
  escapeXML: true,
});

// Colorize Ansible recap lines (PLAY, TASK, ok, changed, failed, etc.) so the log
// reads like a real terminal. ansi-to-html handles real ANSI codes; this adds
// soft class-based coloring for the structural recap that Ansible emits.
function colorizeAnsible(text) {
  if (!text) return "";
  const html = ansiConverter.toHtml(text);
  return html
    .split("\n")
    .map((line) => {
      const trimmed = line.replace(/<[^>]+>/g, "");
      let cls = "";
      if (/^PLAY\b|^TASK\b/i.test(trimmed)) cls = "task";
      else if (/^ok:/.test(trimmed)) cls = "ok";
      else if (/^changed:/.test(trimmed)) cls = "changed";
      else if (/^failed:/.test(trimmed) || /^FAILED/.test(trimmed)) cls = "failed";
      else if (/^fatal:/i.test(trimmed)) cls = "fatal";
      else if (/^PLAY RECAP|^\w[\w\-.]*\s*: ok=/.test(trimmed)) cls = "recap";
      return `<span class="ansi-line${cls ? " " + cls : ""}">${line || "&nbsp;"}</span>`;
    })
    .join("");
}

const renderedLog = computed(() => colorizeAnsible(liveOutput.value || expandedJob.value?.output_log || ""));

// Follow after the DOM update, including saved output, wrapping, and resuming.
watch([renderedLog, logContainer, autoScroll, wrapLines], scrollIfNeeded, { flush: "post" });

async function load() {
  const sequence = ++loadSequence;
  loading.value = true;
  try {
    const params = { limit: 50, offset: page.value * 50 };
    if (filterPlaybook.value) params.playbook = filterPlaybook.value;
    let rows, more;
    if (filterStatus.value === 'adverse') {
      const [failed, partial, recovery] = await Promise.all([getJobs({ ...params, status: 'failed' }), getJobs({ ...params, status: 'partial' }), getJobs({ ...params, status: 'recovery_required' })]);
      rows = [...failed, ...partial, ...recovery].sort((a,b) => String(b.created_at).localeCompare(String(a.created_at)));
      more = failed.length === 50 || partial.length === 50 || recovery.length === 50;
    } else {
      if (filterStatus.value) params.status = filterStatus.value;
      rows = await getJobs(params); more = rows.length === 50;
    }
    if (sequence !== loadSequence) return;
    if (expandedJob.value && !rows.some(job => job.job_id === expanded.value)) rows.unshift(expandedJob.value);
    jobs.value = rows; hasNextPage.value = more; loadError.value = null;
  } catch (error) { if (sequence === loadSequence) loadError.value = error; }
  finally { if (sequence === loadSequence) loading.value = false; }
}

function stopStream() {
  if (streamController) {
    streamController.abort();
    streamController = null;
  }
  streaming.value = false;
}

function toggleAutoScroll() {
  autoScroll.value = !autoScroll.value;
  autoScrollDisabled = !autoScroll.value;
}

function onLogScroll(event) {
  const el = event.currentTarget;
  const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight);
  // Content growth alone must not pause following. Only upward movement does.
  if (el.scrollTop < lastScrollTop && distanceFromBottom > 40) autoScroll.value = false;
  else if (distanceFromBottom < 4 && !autoScrollDisabled) autoScroll.value = true;
  lastScrollTop = el.scrollTop;
}

function scrollIfNeeded() {
  const el = logContainer.value;
  if (!autoScroll.value || !el) return;
  el.scrollTop = el.scrollHeight;
  lastScrollTop = el.scrollTop;
}

async function startStream(jobId) {
  stopStream();
  liveOutput.value = "";
  streaming.value = true;
  streamController = new AbortController();

  await streamJobOutput(jobId, {
    signal: streamController.signal,
    onLine: (line) => {
      if (expanded.value !== jobId) return;
      liveOutput.value += line + "\n";
    },
    onDone: async () => {
      if (expanded.value !== jobId) return;
      streaming.value = false;
      streamController = null;
      await load();
      try {
        const result = await getJob(jobId);
        if (expanded.value === jobId) expandedJob.value = result;
      } catch { /* ignore */ }
    },
    onError: (err) => {
      if (expanded.value !== jobId) return;
      streaming.value = false;
      streamController = null;
      window.$toast?.error("Stream disconnected", err);
    },
  });
}

async function toggleExpand(jobId) {
  const selected = expanded.value === jobId ? undefined : jobId;
  await router.replace({ query: { ...route.query, job: selected } });
}

async function showJob(jobId) {
  stopStream();
  detailError.value = null;
  expanded.value = typeof jobId === 'string' ? jobId : null;
  expandedJob.value = null;
  liveOutput.value = "";
  autoScroll.value = true;
  autoScrollDisabled = false;
  lastScrollTop = 0;
  if (!expanded.value) return;
  try {
    const job = await getJob(jobId);
    if (expanded.value !== jobId) return;
    expandedJob.value = job;
    if (!jobs.value.some((item) => item.job_id === jobId)) jobs.value.unshift(job);
    if (['running', 'pending', 'cancelling'].includes(job.status)) startStream(jobId);
  } catch (e) {
    if (expanded.value === jobId) {
      detailError.value = e;
      window.$toast?.error("Couldn't load job details", e);
    }
  }
}

function askAboutJob(job) {
  window.dispatchEvent(new CustomEvent("helpchat:open", {
    detail: { prompt: `Explain ${job.playbook} job ${job.job_id}: what happened on each device, what evidence supports it, and what should I do next?` },
  }));
}

function formatTime(dt) {
  return formatLongTime(dt) || "--";
}

function resultTitle(type) {
  return ({ assessment: "Maintenance assessment", driver: "Driver update", gpu: "GPU usage", storage: "Storage analysis", packages: "Apt updates", apt_install: "Apt installation", cleanup: "Container cache", reboot: "Node reboot", services: "System services", accounts: "Account state", kubernetes: "Kubernetes recovery" })[type] || "Result";
}

onUnmounted(() => { disposed = true; loadSequence++; stopStream(); clearInterval(refreshTimer); });
watch(() => [filterStatus.value, filterPlaybook.value, page.value], load);
watch(() => route.query.job, showJob);
onMounted(async () => { await load(); if (disposed) return; await showJob(route.query.job); if (disposed) return; refreshTimer = setInterval(async () => { await load(); if (expanded.value) { const id = expanded.value; try { const job = await getJob(id); if (expanded.value === id) { expandedJob.value = job; if (!jobs.value.some(j => j.job_id === id)) jobs.value.unshift(job); } } catch { /* preserve the last observation on a transient failure */ } } }, 5000); });
</script>

<style scoped>
.technical-output { margin-top:20px; }.technical-output > summary { cursor:pointer; font-size:13px; padding:10px 0; }
.activity-filters { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; }.activity-filters label { display: grid; gap: 5px; font-size: 12px; flex: 1; min-width: 180px; }.activity-coverage { color: var(--text-secondary); font-size: 12px; margin-bottom: 14px; }.activity-pagination { display: flex; align-items: center; justify-content: flex-end; gap: 16px; margin-top: 16px; font-size: 13px; }

.structured-text { white-space:pre-wrap; max-height:350px; overflow:auto; overflow-wrap:anywhere; }.service-results { max-height:350px; overflow:auto; }.outcomes { display:flex; flex-wrap:wrap; gap:8px 24px; }.job-detail {
  padding: var(--space-sm);
  background-color: var(--surface-light);
  border-top: 1px solid var(--border-subtle);
}

.job-vars {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: var(--space-xs);
  word-break: break-all;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 10px;
  margin-bottom: var(--space-sm);
}

.result-card {
  padding: 12px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  background: var(--surface-white);
}

.result-heading,
.result-metrics,
.driver-change {
  display: flex;
  align-items: center;
  gap: 12px;
}

.result-heading {
  justify-content: space-between;
  margin-bottom: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}

.result-heading strong,
.driver-change code {
  color: var(--text-primary);
}

.result-metrics {
  flex-wrap: wrap;
  font-size: 12px;
}

.result-card p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.metric-good { color: var(--color-success); }
.metric-warn { color: var(--color-warning); }
.metric-bad { color: var(--color-danger); }

.job-recap,
.job-recap-expanded {
  padding: 6px var(--space-sm);
  background-color: var(--surface-dark);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-success);
}

.job-recap pre,
.job-recap-expanded pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: inherit;
}

.job-recap-expanded {
  border-bottom: 1px solid var(--border-subtle);
  margin-bottom: 0;
}

</style>
