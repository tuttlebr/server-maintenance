<template>
  <div>
    <div class="page-header">
      <h2>Activity</h2>
      <div class="flex gap-xs">
        <label class="visually-hidden" for="job-filter-status">Filter by status</label>
        <select id="job-filter-status" v-model="filterStatus" class="form-select" style="width: auto; min-width: 140px">
          <option value="">All Statuses</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
          <option value="running">Running</option>
          <option value="pending">Pending</option>
          <option value="cancelled">Cancelled</option><option value="cancelling">Cancelling</option><option value="recovery_required">Recovery required</option>
        </select>
        <button class="btn btn-ghost btn-sm" aria-label="Refresh job list" @click="load">
          <i class="fas fa-sync-alt" aria-hidden="true"></i> Refresh
        </button>
      </div>
    </div>

    <div v-if="jobs.length" class="table-wrapper">
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
          <template v-for="job in jobs" :key="job.job_id">
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
            <tr v-if="job.recap && expanded !== job.job_id" style="cursor: pointer" @click="toggleExpand(job.job_id)">
              <td colspan="7" style="padding: 0">
                <div class="job-recap"><pre>{{ job.recap }}</pre></div>
              </td>
            </tr>
            <tr v-if="expanded === job.job_id">
              <td colspan="7" style="padding: 0">
                <div class="job-detail">
                  <p v-if="expandedJob?.error_summary" role="status" class="callout callout-danger">{{ expandedJob.error_summary }}</p>
                  <p v-if="expandedJob?.status === 'recovery_required'" class="callout callout-warn">Remote state needs verification. Review the log and Kubernetes recovery details, repair the host if needed, then run Verify recovery in <router-link to="/operations">Operations</router-link>. Resume Kubernetes scheduling separately when ready.</p>
                  <p v-if="expandedJob && ['pending', 'running', 'cancelling'].includes(expandedJob.status)">Phase: {{ expandedJob.phase?.replaceAll('_', ' ') }}. <button v-if="canCancel(expandedJob)" class="btn btn-ghost btn-sm" :disabled="cancelling" @click="requestCancel(expandedJob)">Cancel {{ expandedJob.status === 'pending' ? 'queued job' : 'inspection' }}</button><span v-else>Running changes finish under supervision; they cannot be safely cancelled.</span></p>
                  <ul v-if="expandedJob?.device_results?.length" class="outcomes" aria-label="Per-device outcomes"><li v-for="result in expandedJob.device_results" :key="result.hostname"><strong>{{ result.hostname }}</strong>: {{ result.status.replaceAll('_', ' ') }}</li></ul>
                  <router-link v-if="expandedJob?.playbook === 'package_preview.yml' && expandedJob.status === 'success'" :to="`/operations?preview=${expandedJob.job_id}`" class="btn btn-primary btn-sm">Review and apply this preview</router-link>
                  <div v-if="job.recap" class="job-recap-expanded"><pre>{{ job.recap }}</pre></div>
                  <section v-if="expandedJob?.result_artifacts?.length" class="result-grid" aria-label="Structured operation results">
                    <article v-for="result in expandedJob.result_artifacts" :key="`${result.report_type}-${result.hostname}`" class="result-card">
                      <div class="result-heading">
                        <span>{{ resultTitle(result.report_type) }}</span>
                        <strong>{{ result.hostname }}</strong>
                      </div>
                      <template v-if="result.report_type === 'packages'"><p>{{ result.changes?.length || 0 }} transaction entries. Installation rechecks this plan; changed plans require a new preview.</p><pre class="structured-text">{{ result.changes?.join('\n') || 'No package updates proposed.' }}</pre></template>
                      <template v-else-if="result.report_type === 'kubernetes'"><dl><dt>Phase</dt><dd>{{ result.phase }}</dd><dt>Node</dt><dd>{{ result.node }}</dd><dt>Context</dt><dd>{{ result.context }}</dd><dt>Originally cordoned</dt><dd>{{ result.originally_unschedulable ? 'Yes' : 'No' }}</dd></dl></template>
                      <template v-else-if="result.report_type === 'services'"><p>{{ result.action === 'status' ? 'Observed services' : `${result.action}: ${result.service}` }}</p><details :open="result.action !== 'status'"><summary>Service states</summary><div class="service-results"><table><thead><tr><th>Unit</th><th>State</th><th>Startup</th></tr></thead><tbody><tr v-for="unit in Object.values(result.services || {}).sort((a,b) => a.name.localeCompare(b.name))" :key="unit.name"><td>{{ unit.name }}</td><td>{{ unit.state }}</td><td>{{ unit.status }}</td></tr></tbody></table></div></details></template>
                      <template v-else-if="result.report_type === 'accounts'"><p>{{ result.accounts?.length || 0 }} account observations. <router-link to="/access">Review per-device privileges in Access</router-link>.</p><ul><li v-for="account in result.accounts" :key="account.username">{{ account.username }}: {{ account.present ? 'present' : 'absent' }}</li></ul></template>
                      <template v-else-if="result.report_type === 'assessment'">
                        <div class="result-metrics">
                          <span class="metric-good"><strong>{{ result.summary?.pass_count || 0 }}</strong> passed</span>
                          <span class="metric-warn"><strong>{{ result.summary?.warning_count || 0 }}</strong> warnings</span>
                          <span class="metric-bad"><strong>{{ result.summary?.blocker_count || 0 }}</strong> blockers</span>
                        </div>
                      </template>
                      <template v-else-if="result.report_type === 'gpu'">
                        <div class="result-metrics">
                          <span><strong>{{ result.active_gpus || 0 }}</strong> active</span>
                          <span><strong>{{ result.idle_gpus || 0 }}</strong> idle</span>
                          <span><strong>{{ result.free_gpus || 0 }}</strong> free</span>
                        </div>
                        <p v-if="result.user_summary?.length">Top owners: {{ result.user_summary.slice(0, 5).map(item => item.user).join(', ') }}</p>
                      </template>
                      <template v-else-if="result.report_type === 'storage'">
                        <div class="result-metrics">
                          <span :class="storagePressure(result).length ? 'metric-warn' : 'metric-good'"><strong>{{ storagePressure(result).length }}</strong> pressured mounts</span>
                        </div>
                        <p v-if="storagePressure(result).length">{{ storagePressure(result).map(item => `${item.mountpoint} ${item.use_pct}%`).join(' · ') }}</p>
                        <p v-if="topStorageOwners(result).length">Largest: {{ topStorageOwners(result).map(item => `${item.path} (${item.size_mb} MB)`).join(' · ') }}</p>
                      </template>
                      <template v-else-if="result.report_type === 'driver'">
                        <div class="driver-change"><code>{{ result.pre_driver_version || 'unknown' }}</code><i class="fas fa-arrow-right" aria-hidden="true"></i><code>{{ result.post_driver_version || 'unknown' }}</code></div>
                        <p>{{ result.reboot_performed ? 'Reboot completed' : 'No reboot performed' }}</p>
                      </template>
                    </article>
                  </section>
                  <div v-if="job.extra_vars" class="job-vars">
                    <strong>Parameters:</strong> {{ job.extra_vars }}
                  </div>

                  <!-- Output log -->
                  <div>
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
                          @click="autoScroll = !autoScroll"
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
                      ref="logContainer"
                      class="log-output"
                      :style="{ whiteSpace: wrapLines ? 'pre-wrap' : 'pre' }"
                      tabindex="0"
                      @scroll="onLogScroll"
                      v-html="renderedLog || (expandedJob && expandedJob.output_log ? colorizeAnsible(expandedJob.output_log) : '<span style=\'opacity:.5\'>No output available</span>')"
                    ></div>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <div v-else class="empty-state">
      <i class="fas fa-list-check" aria-hidden="true"></i>
      <p>No activity found</p>
      <router-link to="/" class="btn btn-primary btn-sm" style="display: inline-flex; margin-top: var(--space-sm)">
        <i class="fas fa-home" aria-hidden="true"></i> Back to overview
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import AnsiToHtml from "ansi-to-html";
import { getJobs, getJob, streamJobOutput, cancelJob } from "../api.js";
import StatusBadge from "../components/StatusBadge.vue";
import { formatTargetList, operationLabel } from "../utils/devices.js";
import { formatLongTime } from "../utils/time.js";

const jobs = ref([]);
const cancelling = ref(false);
let refreshTimer;
function canCancel(job) { return !job.playbook.startsWith("reachy.") && (job.status === "pending" || (job.status === "running" && job.execution_kind === "read_only")); }
async function requestCancel(job) { cancelling.value = true; try { await cancelJob(job.job_id); expandedJob.value = await getJob(job.job_id); await load(); } catch(e) { window.$toast?.error("Could not cancel job", e); } finally { cancelling.value = false; } }
const route = useRoute();
const router = useRouter();
const filterStatus = ref("");
const expanded = ref(null);
const expandedJob = ref(null);
const liveOutput = ref("");
const streaming = ref(false);
const logContainer = ref(null);

const autoScroll = ref(true);
const wrapLines = ref(true);

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

const renderedLog = computed(() => (liveOutput.value ? colorizeAnsible(liveOutput.value) : ""));

async function load() {
  try {
    const params = { limit: 50 };
    if (filterStatus.value) params.status = filterStatus.value;
    jobs.value = await getJobs(params);
  } catch (e) {
    window.$toast?.error("Couldn't load jobs", e);
  }
}

function stopStream() {
  if (streamController) {
    streamController.abort();
    streamController = null;
  }
  streaming.value = false;
}

function onLogScroll() {
  const el = logContainer.value;
  if (!el) return;
  const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight);
  // If user scrolls up more than ~40px, disable auto-scroll; if they snap back, re-enable.
  if (distanceFromBottom > 40) autoScroll.value = false;
  else if (distanceFromBottom < 4) autoScroll.value = true;
}

function scrollIfNeeded() {
  if (!autoScroll.value) return;
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight;
    }
  });
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
      scrollIfNeeded();
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
  expanded.value = typeof jobId === 'string' ? jobId : null;
  expandedJob.value = null;
  liveOutput.value = "";
  autoScroll.value = true;
  if (!expanded.value) return;
  try {
    const job = await getJob(jobId);
    if (expanded.value !== jobId) return;
    expandedJob.value = job;
    if (!jobs.value.some((item) => item.job_id === jobId)) jobs.value.unshift(job);
    if (['running', 'pending', 'cancelling'].includes(job.status)) startStream(jobId);
    else nextTick(scrollIfNeeded);
  } catch (e) {
    if (expanded.value === jobId) {
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
  return ({ assessment: "Maintenance assessment", driver: "Driver update", gpu: "GPU usage", storage: "Storage analysis", packages: "Package preview", services: "System services", accounts: "Account state", kubernetes: "Kubernetes recovery" })[type] || "Result";
}

function storagePressure(result) {
  return (result?.mounts || []).filter((mount) => mount?.accessible && Number(mount.use_pct || 0) >= 85);
}

function topStorageOwners(result) {
  return (result?.mounts || []).flatMap((mount) => mount?.entries || []).sort((a, b) => Number(b.size_mb || 0) - Number(a.size_mb || 0)).slice(0, 3);
}

onUnmounted(() => { stopStream(); clearInterval(refreshTimer); });
watch(filterStatus, load);
watch(() => route.query.job, showJob);
onMounted(async () => { await load(); await showJob(route.query.job); refreshTimer = setInterval(async () => { await load(); if (expanded.value) { const id = expanded.value; try { const job = await getJob(id); if (expanded.value === id) { expandedJob.value = job; if (!jobs.value.some(j => j.job_id === id)) jobs.value.unshift(job); } } catch { /* preserve the last observation on a transient failure */ } } }, 5000); });
</script>

<style scoped>
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
