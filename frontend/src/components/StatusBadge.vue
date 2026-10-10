<template>
  <span class="status-badge-wrap">
    <span :class="['badge', 'badge-status', badgeClass, { 'badge-active': isActive }]">
      <span :class="['dot', dotClass, isActive ? 'dot-pulse' : '']" aria-hidden="true"></span>
      {{ label }}
    </span>
    <InfoTooltip v-if="withTooltip && description" :text="description" />
  </span>
</template>

<script setup>
import { computed } from "vue";
import InfoTooltip from "./InfoTooltip.vue";

const props = defineProps({
  status: { type: String, required: true },
  withTooltip: { type: Boolean, default: false },
});

const ACTIVE_STATUSES = new Set(["running", "pending", "cancelling", "scanning", "starting"]);

const badgeClass = computed(() => {
  const map = {
    online: "badge-outline",
    offline: "badge-outline",
    unknown: "badge-outline",
    success: "badge-green",
    partial: "badge-orange",
    failed: "badge-red", recovery_required: "badge-red", cancelling: "badge-blue",
    running: "badge-blue",
    pending: "badge-outline",
    scanning: "badge-blue",
  };
  return map[props.status] || "badge-outline";
});

const dotClass = computed(() => {
  const map = {
    online: "dot-green",
    offline: "dot-red",
    unknown: "dot-gray",
    success: "dot-green",
    partial: "dot-orange",
    failed: "dot-red", recovery_required: "dot-red", cancelling: "dot-blue",
    running: "dot-blue",
    pending: "dot-orange",
    scanning: "dot-blue",
  };
  return map[props.status] || "dot-gray";
});

const DESCRIPTIONS = {
  online: "The host responded to the most recent fleet scan.",
  offline: "The host did not respond to the last fleet scan. Check power and network.",
  unknown: "The host hasn't been scanned recently, or the last scan failed. Click Scan to refresh.",
  success: "The job finished without errors.",
  partial: "Some, but not all, devices completed successfully. Open the job to review per-device outcomes.",
  failed: "The job hit an error. Open the job to read the log and (optionally) run AI analysis.",
  running: "Job is in progress.",
  recovery_required: "The change did not finish with a confirmed result. The next install or cleanup automatically checks device health before continuing.",
  cancelling: "Waiting for execution to stop.",
  pending: "Job is queued and will start shortly.",
  scanning: "A fleet scan is in progress.",
};

const description = computed(() => DESCRIPTIONS[props.status] || "");

const isActive = computed(() => ACTIVE_STATUSES.has(props.status));

const label = computed(() =>
  props.status === "recovery_required" ? "Health check pending" : props.status.charAt(0).toUpperCase() + props.status.slice(1).replaceAll("_", " ")
);
</script>

<style scoped>
.status-badge-wrap {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
</style>
