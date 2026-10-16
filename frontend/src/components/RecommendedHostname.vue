<template>
  <div v-if="hostname || facts.hostname_recommendation_reason" class="hostname-recommendation">
    <span class="label">Recommended hostname</span>
    <template v-if="hostname">
      <strong>{{ hostname }}</strong>
      <p v-if="facts.hostname_recommendation_source">Last six characters of {{ facts.hostname_recommendation_source.toLowerCase() }}.</p>
      <details>
        <summary>Hostname command</summary>
        <p>Run this command on the device to apply the name.</p>
        <code>{{ command }}</code>
        <button type="button" class="btn btn-ghost btn-sm" @click="copyCommand">Copy command</button>
        <p v-if="copyStatus" role="status">{{ copyStatus }}</p>
      </details>
    </template>
    <p v-else>Unavailable: {{ facts.hostname_recommendation_reason }}</p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { copyText } from '../utils/clipboard.js';

const props = defineProps({ facts: { type: Object, default: () => ({}) } });
const hostname = computed(() => {
  const value = props.facts.recommended_hostname;
  return typeof value === 'string' && /^ai-sae-(spark|dgx|jetson)-[a-z0-9]{6}$/.test(value) ? value : '';
});
const command = computed(() => `sudo hostnamectl set-hostname ${hostname.value}`);
const copyStatus = ref('');
watch(command, () => { copyStatus.value = ''; });
async function copyCommand() {
  try {
    await copyText(command.value);
    copyStatus.value = 'Command copied.';
  } catch {
    copyStatus.value = 'Could not copy. Select and copy the command above.';
  }
}
</script>

<style scoped>
.hostname-recommendation { margin-top:16px; font-size:13px; overflow-wrap:anywhere; }
.label { display:block; color:var(--text-secondary); margin-bottom:6px; }
strong { font-family:var(--font-mono); }
p { color:var(--text-secondary); margin:8px 0; }
summary { cursor:pointer; }
code { display:block; margin:10px 0; white-space:normal; }
</style>
