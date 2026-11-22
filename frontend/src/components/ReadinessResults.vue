<template>
  <section v-if="reports.length" class="readiness" aria-label="Maintenance readiness findings">
    <article v-for="report in reports" :key="report.hostname">
      <details :open="hasFindings(report)">
        <summary>
          <strong>{{ devices.find(device => device.inventory_name === report.hostname)?.name || report.hostname }}</strong>
          <span>{{ summary(report) }}</span>
        </summary>
        <p v-if="report.timestamp" class="observed">Observed {{ formatLongTime(report.timestamp) }}</p>
        <dl>
          <template v-for="(label, key) in labels" :key="key">
            <dt>{{ label }}</dt>
            <dd>
              <strong :class="report.checks[key].status">{{ states[report.checks[key].status] }}</strong>
              <span>{{ report.checks[key].detail }}</span>
              <span v-if="report.checks[key].advice">{{ report.checks[key].advice }}</span>
            </dd>
          </template>
        </dl>
      </details>
    </article>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import { formatLongTime } from '../utils/time.js';

const props = defineProps({
  reports: { type: Array, default: () => [] },
  devices: { type: Array, default: () => [] },
});
const reports = computed(() => props.reports.filter(report => report.report_type === 'host_readiness'));
const labels = { root_capacity: 'Root filesystem', memory: 'Available memory', services: 'System services', reboot: 'Reboot request' };
const states = { ok: 'Clear', attention: 'Review', unavailable: 'Unavailable', not_applicable: 'Not applicable' };
function hasFindings(report) {
  return Object.keys(labels).some(key => ['attention', 'unavailable'].includes(report.checks[key].status));
}
function summary(report) {
  const statuses = Object.keys(labels).map(key => report.checks[key].status);
  const issues = statuses.filter(status => status === 'attention').length;
  const unknown = statuses.filter(status => status === 'unavailable').length;
  return [
    issues ? `${issues} ${issues === 1 ? 'finding' : 'findings'} to review` : '',
    unknown ? `${unknown} ${unknown === 1 ? 'check' : 'checks'} unavailable` : '',
  ].filter(Boolean).join(' · ') || 'No findings in applicable checks';
}
</script>

<style scoped>
.readiness { margin-top: 16px; }
article { padding: 12px 0; border-top: 1px solid var(--border-subtle); }
summary { cursor: pointer; overflow-wrap: anywhere; }
summary span { margin-inline-start: 10px; color: var(--text-secondary); font-size: 13px; }
.observed { color: var(--text-secondary); font-size: 12px; }
dl { display: grid; grid-template-columns: minmax(100px, auto) 1fr; gap: 12px 18px; font-size: 13px; }
dt { font-weight: 600; }
dd { margin: 0; overflow-wrap: anywhere; }
dd span { display: block; line-height: 1.5; }
.attention, .unavailable { color: var(--status-warning-text); }
@media (max-width: 540px) {
  dl { grid-template-columns: 1fr; gap: 4px; }
  dd { margin-bottom: 8px; }
}
</style>
