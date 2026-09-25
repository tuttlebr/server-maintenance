<template>
  <article class="attention-group" :aria-labelledby="`group-${group.id}`">
    <div class="group-heading">
      <h3 :id="`group-${group.id}`">{{ group.title }}</h3>
      <span :class="['condition-tag', group.severity]">{{ group.devices.length }} {{ group.devices.length === 1 ? 'device' : 'devices' }} · {{ group.label }}</span>
    </div>
    <p class="names">{{ group.devices.slice(0, 3).map(device => device.name).join(', ') }}<span v-if="group.devices.length > 3"> +{{ group.devices.length - 3 }} more</span></p>
    <p class="guidance">{{ group.description }}</p>
    <p v-if="overlap.length" class="overlap">Work already targets this group: <router-link v-for="job in overlap" :key="job.job_id" :to="{ path: '/activity', query: { job: job.job_id } }">{{ operationLabel(job.playbook) }} ({{ formatTargetList(job.target_devices) }})</router-link></p>
    <div class="group-actions">
      <router-link :to="groupRoute(group)">{{ group.action }}</router-link>
      <router-link :to="{ path: '/devices', query: { reason: group.id } }">View devices</router-link>
    </div>
    <details class="group-details">
      <summary>Device evidence ({{ group.devices.length }})</summary>
      <label v-if="group.devices.length > 5" class="group-search">Find an affected device<input v-model="search" class="form-input" type="search" placeholder="Name or endpoint" /></label>
      <ul class="evidence-list">
        <li v-for="device in matches" :key="device.id">
          <router-link :to="{ path: `/devices/${device.id}`, query: { reason: group.id } }">{{ device.name }}</router-link>
          <span>{{ deviceConditions(device).map(condition => condition.label).join(' · ') }}</span>
          <small v-if="device.recovery_required && device.recovery_reason">{{ device.recovery_reason }}</small>
          <small>Facts: <time v-if="device.discovered_at" :datetime="device.discovered_at">{{ formatLongTime(device.discovered_at) }}</time><template v-else>not observed</template><template v-if="device.facts_stale"> · stale</template></small>
          <small v-if="device.status === 'offline'">Last seen: {{ formatLongTime(device.last_seen) || 'unknown' }}</small>
        </li>
      </ul>
      <p v-if="!matches.length" class="guidance">No affected devices match this search.</p>
    </details>
  </article>
</template>
<script setup>
import { computed, ref } from 'vue';
import { deviceConditions, groupRoute, overlappingJobs } from '../utils/fleetOverview.js';
import { deviceMatchesSearch, operationLabel, formatTargetList } from '../utils/devices.js';
import { formatLongTime } from '../utils/time.js';
const props = defineProps({ group: { type: Object, required: true }, jobs: { type: Array, default: () => [] } });
const search = ref('');
const matches = computed(() => props.group.devices.filter(device => deviceMatchesSearch(device, search.value)));
const overlap = computed(() => overlappingJobs(props.group.devices, props.jobs));
</script>
<style scoped>
.attention-group { padding: 16px 20px; border-top: 1px solid var(--border-subtle); }
.group-heading { display: flex; justify-content: space-between; align-items: start; gap: 12px; }
.group-heading h3 { font-size: 15px; }
.names { font-family: var(--font-mono); font-size: 12px; margin: 6px 0 3px; overflow-wrap: anywhere; }
.guidance, .overlap { color: var(--text-secondary); font-size: 13px; }
.overlap { margin-top: 8px; }.overlap a { margin-right: 8px; }
.group-actions { display: flex; flex-wrap: wrap; gap: 8px 20px; margin-top: 10px; font-size: 13px; }.group-actions a:first-child { font-weight: 650; }
.group-details { margin-top: 10px; font-size: 12px; }summary { cursor: pointer; color: var(--text-secondary); width: fit-content; min-height: 24px; padding: 3px 0; }
.group-search { display: grid; gap: 5px; margin-top: 10px; }
.evidence-list { list-style: none; max-height: 310px; overflow-y: auto; margin-top: 6px; }
.evidence-list li { display: grid; gap: 3px; padding: 10px 2px; border-top: 1px solid var(--border-subtle); }.evidence-list span, .evidence-list small { color: var(--text-secondary); }.evidence-list small { font-size: 12px; }
@media (max-width: 620px) { .group-heading { flex-direction: column; gap: 5px; }.attention-group { padding: 16px; } }
</style>
