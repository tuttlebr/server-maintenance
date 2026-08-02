<template>
  <div v-if="job || error" :class="['job-inline', statusClass]">
    <div class="job-inline-row">
      <span class="job-inline-icon" aria-hidden="true">
        <span v-if="running" class="dot dot-blue dot-pulse"></span>
        <i v-else-if="finalStatus === 'success'" class="fas fa-check-circle"></i>
        <i v-else-if="finalStatus === 'failed'" class="fas fa-times-circle"></i>
        <i v-else class="fas fa-circle-notch fa-spin"></i>
      </span>
      <div class="job-inline-body">
        <div class="job-inline-line">
          <strong>{{ playbookLabel }}</strong>
          <span v-if="targetHosts" class="job-inline-meta">· {{ targetHosts }}</span>
          <span class="job-inline-meta job-inline-time">· {{ elapsedLabel }}</span>
          <span v-if="etaLabel" class="job-inline-meta job-inline-eta">· {{ etaLabel }}</span>
        </div>
        <div v-if="currentRecap" class="job-inline-recap" :title="currentRecap">{{ currentRecap }}</div>
        <div v-else-if="error" class="job-inline-recap job-inline-error">{{ error }}</div>
      </div>
      <div class="job-inline-actions">
        <button
          v-if="job && (job.status === 'success' || job.status === 'failed' || running)"
          type="button"
          class="log-toggle"
          :class="{ active: showLog }"
          :aria-pressed="showLog"
          @click="toggleLog"
        >
          {{ showLog ? "Hide log" : "Live log" }}
        </button>
        <button
          v-if="!running"
          type="button"
          class="job-inline-close"
          aria-label="Dismiss status"
          @click="$emit('dismiss')"
        >
          &times;
        </button>
      </div>
    </div>

    <div v-if="showLog" class="job-inline-log-wrap">
      <div ref="logEl" class="log-output job-inline-log" v-html="renderedLog || placeholderLog"></div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import AnsiToHtml from "ansi-to-html";
import { useIntervalFn, useDocumentVisibility } from "@vueuse/core";
import { getJob, streamJobOutput } from "../api.js";
import { formatHostList } from "../utils/hosts.js";

// Rough ETA per playbook for the running case. Values are intentionally
// generous — meant to set expectation, not enforce a deadline.
const PLAYBOOK_ETAS_MS = {
  driver_upgrade: 12 * 60_000,
  reboot: 4 * 60_000,
  package_update: 8 * 60_000,
  storage_analysis: 4 * 60_000,
  docker_cleanup: 3 * 60_000,
  firmware_update: 30 * 60_000,
  firmware_inventory: 3 * 60_000,
  health_diagnostics: 5 * 60_000,
  gpu_usage: 90_000,
  host_bootstrap: 15 * 60_000,
  host_facts: 60_000,
};

function playbookKey(name) {
  if (!name) return null;
  const base = String(name).replace(/\.ya?ml$/i, "");
  return PLAYBOOK_ETAS_MS[base] ? base : null;
}

const props = defineProps({
  jobId: { type: String, required: true },
  // Friendly label to show when we don't yet have the job record back.
  label: { type: String, default: "" },
});

const emit = defineEmits(["done", "failed", "dismiss"]);

const job = ref(null);
const error = ref("");
const showLog = ref(false);
const liveOutput = ref("");
const elapsedMs = ref(0);
const logEl = ref(null);
const visibility = useDocumentVisibility();

let streamController = null;
let startTime = Date.now();

const ansiConverter = new AnsiToHtml({
  fg: "#d8e4c5",
  bg: "#0b0b0b",
  newline: false,
  escapeXML: true,
});

const running = computed(() => {
  if (!job.value) return true;
  return job.value.status === "running" || job.value.status === "pending";
});

const finalStatus = computed(() => {
  if (!job.value) return null;
  if (job.value.status === "success" || job.value.status === "failed") return job.value.status;
  return null;
});

const statusClass = computed(() => {
  if (running.value) return "job-inline-running";
  if (finalStatus.value === "success") return "job-inline-success";
  if (finalStatus.value === "failed") return "job-inline-failed";
  return "job-inline-pending";
});

const playbookLabel = computed(() => job.value?.playbook || props.label || "Job");
const targetHosts = computed(() => {
  const t = job.value?.target_hosts;
  if (!t) return "";
  const sorted = formatHostList(t);
  return sorted.length > 60 ? `${sorted.slice(0, 57)}...` : sorted;
});

const elapsedLabel = computed(() => {
  const s = Math.floor(elapsedMs.value / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}m ${rem}s`;
});

const etaLabel = computed(() => {
  if (!running.value) return "";
  const key = playbookKey(job.value?.playbook);
  if (!key) return "";
  const remaining = PLAYBOOK_ETAS_MS[key] - elapsedMs.value;
  if (remaining <= 60_000) return "wrapping up";
  const mins = Math.round(remaining / 60_000);
  return `~${mins}m remaining`;
});

// Pull the most recent line from either the streaming buffer (live) or the
// stored recap. Keeps the row compact while giving operators a hint of progress.
const currentRecap = computed(() => {
  const source = liveOutput.value || job.value?.recap || "";
  if (!source) return "";
  const lines = source.split("\n").filter((l) => l.trim());
  return lines.length ? lines[lines.length - 1].slice(0, 200) : "";
});

function colorize(text) {
  if (!text) return "";
  const html = ansiConverter.toHtml(text);
  return html
    .split("\n")
    .map((line) => {
      const plain = line.replace(/<[^>]+>/g, "");
      let cls = "";
      if (/^PLAY\b|^TASK\b/i.test(plain)) cls = "task";
      else if (/^ok:/.test(plain)) cls = "ok";
      else if (/^changed:/.test(plain)) cls = "changed";
      else if (/^failed:/.test(plain) || /^FAILED/.test(plain)) cls = "failed";
      else if (/^fatal:/i.test(plain)) cls = "fatal";
      else if (/^PLAY RECAP|^\w[\w\-.]*\s*: ok=/.test(plain)) cls = "recap";
      return `<span class="ansi-line${cls ? " " + cls : ""}">${line || "&nbsp;"}</span>`;
    })
    .join("");
}

const renderedLog = computed(() => {
  if (liveOutput.value) return colorize(liveOutput.value);
  if (job.value?.output_log) return colorize(job.value.output_log);
  return "";
});

const placeholderLog = `<span style="opacity:.5">Waiting for output…</span>`;

// Tick elapsed display every second while running so the user sees motion
// even if no new log lines arrive.
const elapsedTimer = useIntervalFn(() => {
  if (running.value) elapsedMs.value = Date.now() - startTime;
}, 1000, { immediate: false });

// Poll job status every 2s while it's still running. Pauses on hidden tabs
// so we don't burn requests when the user has switched away.
const poller = useIntervalFn(
  async () => {
    if (visibility.value !== "visible") return;
    try {
      const data = await getJob(props.jobId);
      if (!job.value) {
        // First successful fetch — seed elapsed from the job's created_at
        // so a returning operator sees the real duration.
        const createdAt = data.created_at ? new Date(asUtc(data.created_at)).getTime() : Date.now();
        startTime = createdAt;
        elapsedMs.value = Date.now() - startTime;
      }
      job.value = data;
      if (!running.value) {
        poller.pause();
        elapsedTimer.pause();
        stopStream();
        if (data.status === "success") emit("done", data);
        else emit("failed", data);
      }
    } catch (e) {
      error.value = e?.message || "Couldn't reach job API";
      poller.pause();
      elapsedTimer.pause();
    }
  },
  2000,
  { immediate: true }
);

function asUtc(dt) {
  return String(dt).endsWith("Z") || String(dt).includes("+") ? dt : `${dt}Z`;
}

function toggleLog() {
  showLog.value = !showLog.value;
  if (showLog.value) {
    if (running.value && !streamController) startStream();
    nextTick(() => scrollLog());
  } else {
    stopStream();
  }
}

async function startStream() {
  stopStream();
  liveOutput.value = "";
  streamController = new AbortController();
  await streamJobOutput(props.jobId, {
    signal: streamController.signal,
    onLine: (line) => {
      liveOutput.value += line + "\n";
      scrollLog();
    },
    onDone: () => {
      streamController = null;
    },
    onError: () => {
      streamController = null;
    },
  });
}

function stopStream() {
  if (streamController) {
    streamController.abort();
    streamController = null;
  }
}

function scrollLog() {
  nextTick(() => {
    if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight;
  });
}

watch(running, (isRunning) => {
  if (isRunning) {
    elapsedTimer.resume();
  } else {
    elapsedTimer.pause();
  }
});

onMounted(() => {
  startTime = Date.now();
  elapsedMs.value = 0;
  elapsedTimer.resume();
});

onUnmounted(() => {
  poller.pause();
  elapsedTimer.pause();
  stopStream();
});
</script>

<style scoped>
.job-inline {
  margin-top: var(--space-xs);
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
  background: var(--surface-light);
  font-size: 13px;
}

.job-inline-running {
  border-color: rgba(0, 116, 223, 0.45);
  background: var(--surface-info-soft);
}

.job-inline-success {
  border-color: rgba(118, 185, 0, 0.45);
  background: var(--surface-success-soft);
}

.job-inline-failed {
  border-color: rgba(229, 32, 32, 0.45);
  background: var(--surface-danger-soft);
}

.job-inline-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.job-inline-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-top: 2px;
  flex-shrink: 0;
}
.job-inline-success .job-inline-icon i { color: var(--color-success); }
.job-inline-failed  .job-inline-icon i { color: var(--color-danger); }
.job-inline-running .job-inline-icon i { color: var(--color-info); }

.job-inline-body {
  flex: 1;
  min-width: 0;
}

.job-inline-line {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: 12px;
}

.job-inline-meta {
  color: var(--text-secondary);
  font-size: 11px;
}

.job-inline-time {
  margin-left: 4px;
  font-variant-numeric: tabular-nums;
}

.job-inline-eta {
  color: var(--color-info);
  font-weight: 600;
}

.job-inline-recap {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.job-inline-error {
  color: var(--color-danger);
}

.job-inline-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.job-inline-close {
  appearance: none;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 16px;
  color: var(--text-muted);
  padding: 0 4px;
  line-height: 1;
}
.job-inline-close:hover { color: var(--text-secondary); }

.job-inline-log-wrap {
  margin-top: 10px;
}

.job-inline-log {
  max-height: 260px;
  font-size: 11.5px;
}
</style>
