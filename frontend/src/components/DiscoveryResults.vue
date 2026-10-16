<template>
  <section v-if="discoveries.length" aria-label="Discovered device facts" class="discovery-results">
    <article v-for="report in discoveries" :key="report.hostname" class="discovery-result">
      <h4>{{ devices.find(d => d.inventory_name === report.hostname)?.name || report.hostname }}</h4>
      <p class="observed">Observed {{ formatLongTime(report.observed_at) }}</p>
      <dl><template v-for="item in summary(report)" :key="item.label"><dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></template></dl>
      <RecommendedHostname :facts="report.facts || {}" />
      <details><summary>{{ report.capabilities?.length || 0 }} supported {{ report.capabilities?.length === 1 ? 'capability' : 'capabilities' }}</summary><ul><li v-for="capability in report.capabilities || []" :key="capability">{{ capability }}</li></ul></details>
      <router-link v-if="devices.some(d => d.id === report.device_id)" :to="`/devices/${report.device_id}`">View device facts</router-link>
    </article>
  </section>
</template>
<script setup>
import {computed} from 'vue';
import {formatLongTime} from '../utils/time.js';
import RecommendedHostname from './RecommendedHostname.vue';
const props = defineProps({reports:{type:Array,default:()=>[]},devices:{type:Array,default:()=>[]}});
const discoveries = computed(() => props.reports.filter(r => r.report_type === 'discovery'));
function summary(report) {
  return [
    {label:'Platform',value:[report.vendor,report.model].filter(Boolean).join(' ')},
    {label:'Operating system',value:report.os_version || report.facts?.distribution},
    {label:'Architecture',value:report.architecture},
    {label:'CPU',value:report.facts?.cpu?.model},
    {label:'Memory',value:report.memory_gb != null ? `${report.memory_gb} GB` : null},
    {label:'GPU',value:report.gpu_model},
    {label:'Driver',value:report.driver_version},
    {label:'Package manager',value:report.facts?.package_manager},
    {label:'Storage filesystems',value:report.facts?.storage_mounts?.length},
    {label:'Daemon state',value:report.facts?.daemon?.state},
  ].filter(item => item.value != null && item.value !== '');
}
</script>
<style scoped>
.discovery-results { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr)); gap:16px; margin-top:20px; }
.discovery-result { padding:16px; border:1px solid var(--border-subtle); border-radius:6px; min-width:0; }
h4 { margin:0; }.observed { color:var(--text-secondary); font-size:12px; }dl { display:grid; grid-template-columns:auto 1fr; gap:8px 16px; font-size:13px; }dt { color:var(--text-secondary); }dd { margin:0; overflow-wrap:anywhere; }details { margin:16px 0; font-size:12px; }summary { cursor:pointer; }li { overflow-wrap:anywhere; }a { font-size:13px; }
</style>
