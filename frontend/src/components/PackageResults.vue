<template>
  <div class="package-results">
    <details v-for="report in packages" :key="report.hostname" class="package-device" :open="packages.length === 1">
      <summary>{{ deviceName(report.hostname) }} <span>· {{ report.rows.length ? updateLabel(report.rows.length) : 'Up to date' }}</span></summary>
      <div v-if="report.rows.length" class="package-table">
        <table><thead><tr><th scope="col">Package</th><th scope="col">Installed</th><th scope="col">Available</th></tr></thead>
          <tbody><tr v-for="row in report.rows" :key="row.name"><th scope="row">{{ row.name }}</th><td>{{ row.current || 'New dependency' }}</td><td>{{ row.available }}</td></tr></tbody>
        </table>
      </div>
      <p v-else>All packages are up to date.</p>
    </details>
  </div>
</template>
<script setup>
import {computed} from 'vue';
import {packageRows, updateLabel} from '../utils/maintenance.js';
const props = defineProps({reports:{type:Array,default:()=>[]},devices:{type:Array,default:()=>[]}});
const packages = computed(() => props.reports.filter(r => r.report_type === 'packages').map(report => ({...report,rows:packageRows(report)})));
const deviceName = name => props.devices.find(d => d.inventory_name === name)?.name || name;
</script>
<style scoped>
.package-device { margin-top:12px; border:1px solid var(--border-subtle); border-radius:6px; font-size:13px; }
summary { padding:14px; cursor:pointer; font-weight:600; line-height:1.5; overflow-wrap:anywhere; }summary span { font-weight:400; color:var(--text-secondary); }
.package-table { overflow:auto; max-height:340px; border-top:1px solid var(--border-subtle); }
table { width:100%; border-collapse:collapse; font-size:12px; }th,td { text-align:left; padding:10px 14px; border-bottom:1px solid var(--border-subtle); overflow-wrap:anywhere; }
thead th { background:var(--surface-light); color:var(--text-secondary); font-weight:500; position:sticky; top:0; }tbody th { font-weight:500; }td { font-family:var(--font-mono); font-size:11px; }
p { margin:0; padding:0 14px 14px; color:var(--text-secondary); }
</style>
