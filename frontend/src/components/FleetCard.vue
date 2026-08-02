<template>
  <div
    class="card card-clickable fleet-card"
    role="button"
    tabindex="0"
    :aria-label="`Open ${host.hostname}`"
    @click="$router.push(`/hosts/${host.hostname}`)"
    @keydown.enter.prevent="$router.push(`/hosts/${host.hostname}`)"
    @keydown.space.prevent="$router.push(`/hosts/${host.hostname}`)"
  >
    <div class="card-body">
      <div class="fleet-card-header">
        <h4 class="fleet-card-title">{{ host.hostname }}</h4>
        <StatusBadge :status="host.status || 'unknown'" />
      </div>
      <div class="fleet-card-type">
        <span :class="['badge', typeBadgeClass]">
          <i :class="typeIcon" aria-hidden="true"></i>
          {{ typeLabel }}
        </span>
      </div>
      <div class="fleet-card-details">
        <div v-if="mt.hasGpu" class="detail-row">
          <span class="detail-label">GPU</span>
          <span class="detail-value">{{ host.gpu_model || "--" }}</span>
        </div>
        <div v-if="mt.hasGpu" class="detail-row">
          <span class="detail-label">Driver</span>
          <span class="detail-value">{{ host.driver_version || "--" }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Disk /</span>
          <div class="detail-bar">
            <div class="progress-bar">
              <div
                class="progress-fill"
                :class="diskClass(host.disk_root_percent)"
                :style="{ width: (host.disk_root_percent || 0) + '%' }"
              ></div>
            </div>
            <span class="detail-pct">{{ host.disk_root_percent || 0 }}%</span>
          </div>
        </div>
      </div>
      <div v-if="host.reboot_required" class="fleet-card-reboot" @click.stop>
        <i class="fas fa-exclamation-triangle" aria-hidden="true"></i>
        Reboot required
        <InfoTooltip :text="GLOSSARY.rebootRequired" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import StatusBadge from "./StatusBadge.vue";
import InfoTooltip from "./InfoTooltip.vue";
import { getMachineType } from "../machineTypes.js";
import { GLOSSARY } from "../glossary.js";

const props = defineProps({
  host: { type: Object, required: true },
});

const mt = computed(() => getMachineType(props.host.machine_type));
const typeLabel = computed(() => mt.value.label);
const typeBadgeClass = computed(() => mt.value.badge);
const typeIcon = computed(() => mt.value.icon);

function diskClass(pct) {
  if (!pct) return "good";
  if (pct >= 90) return "danger";
  if (pct >= 75) return "warn";
  return "good";
}
</script>

<style scoped>
.fleet-card {
  cursor: pointer;
  border-top: 3px solid transparent;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.fleet-card:hover {
  transform: translateY(-2px);
  border-top-color: var(--color-accent);
}
.fleet-card:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.fleet-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-xs);
  gap: 8px;
}

.fleet-card-title {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.fleet-card-type { margin-bottom: 12px; }

.fleet-card-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}

.detail-label {
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  flex-shrink: 0;
  width: 60px;
}

.detail-value {
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: 12px;
}

.detail-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  margin-left: 12px;
}

.detail-bar .progress-bar { flex: 1; }

.detail-pct {
  font-size: 12px;
  font-weight: 500;
  width: 36px;
  text-align: right;
  font-family: var(--font-mono);
}

.fleet-card-reboot {
  margin-top: 12px;
  padding: 6px 10px;
  background-color: var(--surface-danger-soft);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-danger);
  font-weight: 500;
  border-left: 3px solid var(--color-danger);
}

.fleet-card-reboot i { margin-right: 4px; }
</style>
