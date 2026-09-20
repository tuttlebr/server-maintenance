<template>
  <router-link :to="`/devices/${device.id}`" class="card device-card">
    <div class="card-body">
      <div class="device-card-header">
        <span class="device-icon" aria-hidden="true"><i :class="['fas', kind.icon]"></i></span>
        <StatusBadge :status="device.status || 'unknown'" />
      </div>
      <h3>{{ device.name }}</h3>
      <p class="device-identity">{{ identity }}</p>
      <div class="device-badges">
        <span :class="['badge', kind.badge]">{{ kind.short }}</span>
        <span v-if="platformName" class="badge badge-green">{{ platformName }}</span>
        <span v-if="device.architecture" class="badge badge-outline">{{ device.architecture }}</span>
      </div>
      <dl class="device-facts">
        <template v-if="device.os_version"><dt>OS</dt><dd>{{ device.os_version }}</dd></template>
        <template v-if="device.gpu_model"><dt>GPU</dt><dd>{{ device.gpu_model }}</dd></template>
        <template v-if="device.memory_gb"><dt>Memory</dt><dd>{{ device.memory_gb }} GB</dd></template>
        <template v-if="device.disk_root_percent != null"><dt>Disk /</dt><dd>{{ device.disk_root_percent }}%</dd></template>
      </dl>
      <div v-if="device.reboot_required" class="device-alert"><i class="fas fa-power-off" aria-hidden="true"></i>Reboot required</div>
      <div class="device-capabilities">{{ device.capabilities.length }} capabilities</div>
    </div>
  </router-link>
</template>

<script setup>
import { computed } from "vue";
import StatusBadge from "./StatusBadge.vue";
import { deviceKind, devicePlatformName } from "../utils/devices.js";

const props = defineProps({ device: { type: Object, required: true } });
const kind = computed(() => deviceKind(props.device.kind));
const platformName = computed(() => devicePlatformName(props.device));
const identity = computed(() => [props.device.vendor, props.device.model].filter(Boolean).join(" · ") || props.device.endpoint);
</script>

<style scoped>
.device-card { color: inherit; text-decoration: none; border-top: 3px solid transparent; }.device-card:hover { border-top-color: var(--color-accent); transform: translateY(-2px); text-decoration: none; }.device-card:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
.device-card-header { display: flex; justify-content: space-between; align-items: center; }.device-icon { width: 36px; height: 36px; border-radius: 10px; background: var(--surface-info-soft); color: var(--color-accent); display: grid; place-items: center; }
h3 { margin: 14px 0 3px; font: 650 15px/1.2 var(--font-mono); }.device-identity { height: 18px; margin: 0 0 12px; color: var(--text-secondary); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.device-badges { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
.device-facts { display: grid; grid-template-columns: auto 1fr; gap: 7px 12px; margin: 0; font-size: 12px; }.device-facts dt { color: var(--text-secondary); text-transform: uppercase; font-size: 10px; letter-spacing: .4px; }.device-facts dd { margin: 0; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.device-alert { margin-top: 12px; padding: 7px 9px; border-left: 3px solid var(--color-warning); background: var(--surface-warning-soft); color: var(--text-primary); font-size: 11px; }.device-alert i { margin-right: 6px; color: var(--color-warning); }.device-capabilities { margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--border-subtle); color: var(--text-secondary); font-size: 11px; }
</style>
