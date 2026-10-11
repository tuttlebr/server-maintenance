<template>
  <StorageResults :reports="reports" :devices="devices" />
  <section v-for="report in inspections" :key="`${report.report_type}-${report.hostname}`" class="inspection">
    <h4>{{ devices.find(device => device.inventory_name === report.hostname)?.name || report.hostname }}</h4>
    <p v-if="report.timestamp" class="muted">Observed {{ formatLongTime(report.timestamp) }}</p>
      <article v-for="gpu in report.gpus || []" :key="gpu.uuid || gpu.index" class="gpu">
        <h5>GPU {{ gpu.index }} · {{ gpu.name }}</h5>
        <p class="metrics"><strong>{{ percent(gpu.utilization_pct) }} utilization</strong><span>Memory: {{ gpu.memory_supported === false ? 'Unavailable' : `${memory(gpu.memory_used_mb)} / ${memory(gpu.memory_total_mb)}` }}</span><span>{{ gpuStatus(gpu.status) }}</span></p>
        <p class="muted identity"><code>{{ gpu.uuid }}</code><span v-if="gpu.mig_mode === 'Enabled'"> · MIG enabled</span></p>
        <div v-if="gpu.processes?.length" class="table-scroll" role="region" :aria-label="`Processes on GPU ${gpu.index} of ${report.hostname}`" tabindex="0">
          <table><thead><tr><th scope="col">Linux owner</th><th scope="col">PID</th><th scope="col">Process</th><th scope="col">GPU memory</th><th scope="col">Container / pod</th></tr></thead>
            <tbody><tr v-for="(process, index) in gpu.processes" :key="`${process.pid}-${index}`">
              <td>{{ process.user || 'unknown' }}<small v-if="process.uid != null">UID {{ process.uid }}</small></td>
              <td>{{ process.pid }}</td><td><code>{{ process.process_name }}</code><small v-if="process.executable && process.executable !== process.process_name">{{ process.executable }}</small><small v-if="process.process_type">{{ process.process_type }}</small><small v-if="instanceId(process.gpu_instance_id)">GPU instance {{ process.gpu_instance_id }} / compute instance {{ process.compute_instance_id }}</small></td>
              <td>{{ memory(process.gpu_memory_mb) }}</td>
              <td><span v-if="process.pod_name">{{ process.namespace }}/{{ process.pod_name }}</span><span v-else>{{ process.container_name || (process.container_id ? process.container_id.slice(0, 12) : process.source === 'bare-metal' ? 'Host process' : 'Unavailable') }}</span><small v-if="process.pod_name && process.container_name">{{ process.container_name }}</small><small v-if="process.workload_owner">Owner label: {{ process.workload_owner }}</small></td>
            </tr></tbody>
          </table>
        </div>
        <p v-else class="muted">{{ gpu.processes_known === false ? 'Process information unavailable.' : 'No GPU processes reported in this snapshot.' }}</p>
      </article>
      <p v-if="!report.gpus?.length" class="warning">No GPU readings were reported.</p>
    <p v-for="note in report.notes || []" :key="note" class="muted note">{{ note }}</p>
  </section>
</template>

<script setup>
import {computed} from 'vue';
import StorageResults from './StorageResults.vue';
import {formatLongTime} from '../utils/time.js';
const props = defineProps({reports:{type:Array,default:()=>[]},devices:{type:Array,default:()=>[]}});
const inspections = computed(() => props.reports.filter(report => report.report_type === 'gpu'));
const numeric = value => typeof value === 'number' && Number.isFinite(value);
const percent = value => numeric(value) ? `${value}%` : 'Unavailable';
const memory = value => numeric(value) ? value >= 1024 ? `${(value / 1024).toFixed(1)} GiB` : `${value.toLocaleString()} MiB` : 'Unavailable';
const gpuStatus = status => ({active:'Active',idle_reserved:'Idle with processes',in_use:'Processes present',allocated:'Memory allocated',free:'Idle, no processes',unknown:'State unknown'})[status] || 'State unknown';
const instanceId = value => value != null && /^\d+$/.test(String(value));
</script>

<style scoped>
.inspection{min-width:0;margin-top:20px}.inspection h4{font-size:15px;margin:0 0 6px}.inspection p{font-size:12px;line-height:1.6;margin:6px 0 12px}.muted{color:var(--text-secondary)}.warning{color:var(--status-warning-text)}.table-scroll{overflow-x:auto;max-width:100%;border:1px solid var(--border-subtle);border-radius:6px}.table-scroll:focus-visible{outline:2px solid var(--focus-ring);outline-offset:2px}table{width:100%;border-collapse:collapse;text-align:left;font-size:12px}th,td{padding:12px;vertical-align:top;border-bottom:1px solid var(--border-subtle)}thead{background:var(--surface-light)}thead th{color:var(--text-primary)}tbody th{text-transform:none;letter-spacing:normal;color:var(--text-primary)}th{font-weight:600}td{min-width:90px}small{display:block;color:var(--text-secondary);font-size:11px;font-weight:400;margin-top:4px;overflow-wrap:anywhere}code{font-size:11px;overflow-wrap:anywhere}tbody tr:last-child>*{border-bottom:0}.gpu{margin:16px 0;padding-top:12px;border-top:1px solid var(--border-subtle)}h5{font-size:14px;margin:0 0 8px}.metrics{display:flex;flex-wrap:wrap;gap:8px 18px}.identity{overflow-wrap:anywhere}.note{margin-top:12px!important}
</style>
