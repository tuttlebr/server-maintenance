<template>
  <section v-if="checks.length" class="ip-results" aria-label="IP address results">
    <article v-for="report in checks" :key="report.hostname" class="ip-result">
      <h4>{{ report.hostname }}: {{ labels[report.status] || 'Address not verified' }}</h4>
      <dl>
        <dt>Previous endpoint</dt><dd><code>{{ report.previous_endpoint }}</code></dd>
        <dt>Verified IP</dt><dd><code>{{ report.verified === true ? report.current_ip : 'Not verified' }}</code></dd>
        <template v-if="report.verified === true && report.remote_hostname"><dt>Remote hostname</dt><dd>{{ report.remote_hostname }}</dd></template>
      </dl>
      <p>{{ report.detail }}</p>
      <p v-if="report.verified !== true && report.candidate_ips?.length">Candidates requiring review: {{ report.candidate_ips.join(', ') }}</p>
    </article>
  </section>
</template>

<script setup>
import {computed} from 'vue';
const props = defineProps({reports:{type:Array,default:()=>[]}});
const checks = computed(() => props.reports.filter(report => report.report_type === 'host_ip'));
const labels = {changed:'IP changed',unchanged:'IP unchanged',located:'Current IP located',not_found:'Device not located',ambiguous:'Multiple matching addresses',verification_failed:'SSH verification failed',error:'Discovery failed'};
</script>

<style scoped>
.ip-results{margin-top:20px}.ip-result{padding:16px 0;border-top:1px solid var(--border-subtle)}h4{margin:0 0 12px}dl{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:8px 16px;font-size:13px}dt{color:var(--text-secondary)}dd{margin:0;overflow-wrap:anywhere}p{font-size:13px;line-height:1.5}
</style>
