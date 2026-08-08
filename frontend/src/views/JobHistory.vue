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
                <i
                  :class="['fas', expanded === job.job_id ? 'fa-chevron-up' : 'fa-chevron-down']"
                  :aria-label="expanded === job.job_id ? 'Collapse details' : 'Expand details'"
                  style="color: var(--text-secondary)"
                ></i>
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
                  <div v-if="job.recap" class="job-recap-expanded"><pre>{{ job.recap }}</pre></div>
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
import AnsiToHtml from "ansi-to-html";
import { getJobs, getJob, streamJobOutput } from "../api.js";
import StatusBadge from "../components/StatusBadge.vue";
import { formatTargetList, operationLabel } from "../utils/devices.js";

const jobs = ref([]);
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
      liveOutput.value += line + "\n";
      scrollIfNeeded();
    },
    onDone: async () => {
      streaming.value = false;
      streamController = null;
      await load();
      try {
        expandedJob.value = await getJob(jobId);
      } catch { /* ignore */ }
    },
    onError: (err) => {
      streaming.value = false;
      streamController = null;
      window.$toast?.error("Stream disconnected", err);
    },
  });
}

async function toggleExpand(jobId) {
  if (expanded.value === jobId) {
    expanded.value = null;
    expandedJob.value = null;
    liveOutput.value = "";
    stopStream();
    return;
  }

  expanded.value = jobId;
  expandedJob.value = null;
  liveOutput.value = "";
  autoScroll.value = true;

  const job = jobs.value.find((j) => j.job_id === jobId);
  if (job && (job.status === "running" || job.status === "pending")) {
    startStream(jobId);
  } else {
    try {
      expandedJob.value = await getJob(jobId);
      nextTick(scrollIfNeeded);
    } catch (e) {
      window.$toast?.error("Couldn't load job details", e);
    }
  }
}

function formatTime(dt) {
  if (!dt) return "--";
  const str = String(dt).endsWith("Z") || String(dt).includes("+") ? dt : dt + "Z";
  return new Date(str).toLocaleString("en-US", { timeZone: "America/Los_Angeles" });
}

onUnmounted(stopStream);
watch(filterStatus, load);
onMounted(load);
</script>

<style scoped>
.job-detail {
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
