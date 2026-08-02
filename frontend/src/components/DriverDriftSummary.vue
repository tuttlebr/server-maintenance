<template>
  <div v-if="hostsWithDriver.length" class="dds-wrap">
    <div v-if="branches.length > 1" class="callout callout-warn">
      <i class="fas fa-code-branch callout-icon" aria-hidden="true"></i>
      <div class="callout-body">
        <div class="callout-title">
          Driver drift detected
          <InfoTooltip :text="GLOSSARY.driverBranch" />
        </div>
        <div class="dds-subtitle">
          <span v-for="(b, i) in branches" :key="b.branch">
            <strong>{{ b.count }}</strong> on branch {{ b.branch }}<span v-if="i < branches.length - 1">, </span>
          </span>
          <span v-if="missingCount"> &middot; {{ missingCount }} unknown</span>
        </div>
      </div>
    </div>
    <div v-else class="callout callout-success">
      <i class="fas fa-circle-check callout-icon" aria-hidden="true"></i>
      <div class="callout-body">
        <div class="callout-title">
          Fleet on driver branch {{ branches[0].branch }}
          <InfoTooltip :text="GLOSSARY.driverBranch" />
        </div>
        <div class="dds-subtitle">{{ branches[0].count }} GPU host{{ branches[0].count === 1 ? "" : "s" }} aligned<span v-if="missingCount"> &middot; {{ missingCount }} unknown</span>.</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import InfoTooltip from "./InfoTooltip.vue";
import { GLOSSARY } from "../glossary.js";

const props = defineProps({
  drivers: { type: Array, default: () => [] },
});

const hostsWithDriver = computed(() => props.drivers.filter((d) => d.driver_version));

const missingCount = computed(() => props.drivers.length - hostsWithDriver.value.length);

const branches = computed(() => {
  const counts = new Map();
  for (const d of hostsWithDriver.value) {
    const branch = String(d.driver_version).split(".")[0] || "?";
    counts.set(branch, (counts.get(branch) || 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([branch, count]) => ({ branch, count }))
    .sort((a, b) => b.count - a.count);
});
</script>

<style scoped>
.dds-wrap {
  margin-bottom: var(--space-md);
}
.dds-subtitle {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
</style>
