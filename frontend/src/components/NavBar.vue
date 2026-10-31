<template>
  <nav class="navbar" aria-label="Main navigation">
    <div class="navbar-inner glass-surface">
      <router-link to="/" class="navbar-brand" aria-label="Fleet Manager operations"><i class="fas fa-layer-group" aria-hidden="true"></i><span>Fleet Manager</span></router-link>
      <div class="navbar-links"><router-link v-for="item in navigation" :key="item.to" :to="item.to" :aria-current="route.path === item.to || (item.to !== '/' && route.path.startsWith(item.to + '/')) ? 'page' : undefined" class="nav-link">{{ item.label }}</router-link></div>
      <div class="navbar-user">
        <details ref="management" class="management" @keydown.esc.prevent="closeManagement(true)">
          <summary class="nav-link">Manage</summary>
          <div class="management-links"><router-link to="/context" @click="closeManagement()">Knowledge sources</router-link><button type="button" @click="openHelp">Fleet Help</button>
            <div class="appearance-setting">
              <label for="appearance">Appearance</label>
              <select id="appearance" class="form-select" v-model="appearance" @change="setAppearance">
                <option value="system">System</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </div>
          </div>
        </details>
        <div ref="jobsContainer" class="active-jobs" @keydown.esc.prevent="closeJobs(true)" @focusout="onJobsFocusOut">
          <button ref="jobsTrigger" type="button" class="nav-link" :aria-expanded="showJobs" aria-controls="active-jobs-list" :aria-label="store.activeJobCount == null ? 'Jobs: activity state unavailable' : `Active jobs: ${store.activeJobCount}`" @click="showJobs = !showJobs"><i class="fas fa-bolt" aria-hidden="true"></i>Jobs<span class="jobs-count">{{ store.activeJobCount ?? '–' }}</span></button>
          <div v-if="showJobs" id="active-jobs-list" class="active-jobs-dropdown">
            <div class="active-jobs-header"><strong>Active jobs</strong><button type="button" aria-label="Close active jobs" @click="closeJobs(true)"><i class="fas fa-xmark" aria-hidden="true"></i></button></div>
            <p v-if="store.activeError" class="active-jobs-empty">Activity could not be refreshed. {{ store.activeUpdated ? `Last observed ${formatLongTime(store.activeUpdated)}.` : 'State is unavailable.' }}</p>
            <p v-else-if="store.activeJobCount == null" class="active-jobs-empty">Loading activity…</p>
            <p v-else-if="store.activeJobCount === 0" class="active-jobs-empty">No active jobs.</p>
            <router-link v-for="job in store.activeJobs.slice(0, 8)" :key="job.job_id" :to="{ path: '/activity', query: { job: job.job_id } }" class="active-jobs-item" @click="closeJobs()"><strong>{{ operationLabel(job.playbook) }}</strong><small>{{ job.status.replaceAll('_', ' ') }} · {{ formatTargetList(job.target_devices) }} · {{ relativeTime(job.created_at) }}</small></router-link>
            <router-link to="/activity?status=active" class="active-jobs-footer" @click="closeJobs()">View all active jobs</router-link>
          </div>
        </div>
        <button type="button" class="nav-link sign-out" aria-label="Sign out" title="Sign out" @click="logout"><i class="fas fa-sign-out-alt" aria-hidden="true"></i></button>
      </div>
    </div>
  </nav>
</template>
<script setup>
import { onMounted, onUnmounted, ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { clearToken } from '../api.js';
import { useDevicesStore } from '../stores/devices.js';
import { relativeTime, formatLongTime } from '../utils/time.js';
import { formatTargetList, operationLabel } from '../utils/devices.js';
const navigation = [{ to: '/operations', label: 'Operations' }, { to: '/devices', label: 'Devices' }, { to: '/access', label: 'Users' }, { to: '/activity', label: 'Activity' }, { to: '/overview', label: 'Overview' }];
const router = useRouter(), route = useRoute(), store = useDevicesStore();
const showJobs = ref(false), jobsContainer = ref(null), jobsTrigger = ref(null), management = ref(null);
const appearance = ref(['light', 'dark'].includes(document.documentElement.dataset.theme) ? document.documentElement.dataset.theme : 'system');
function setAppearance() {
  if (appearance.value === 'system') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = appearance.value;
  try {
    if (appearance.value === 'system') localStorage.removeItem('fleet_theme');
    else localStorage.setItem('fleet_theme', appearance.value);
  } catch { /* Keep the current session usable when storage is unavailable. */ }
}
function logout() { clearToken(); router.push('/login'); }
function closeJobs(focus = false) { showJobs.value = false; if (focus) jobsTrigger.value?.focus(); }
function closeManagement(focus = false) { if (management.value) management.value.open = false; if (focus) management.value?.querySelector('summary')?.focus(); }
function openHelp() { closeManagement(); window.dispatchEvent(new CustomEvent('helpchat:open')); }
function outside(event) { if (!jobsContainer.value?.contains(event.target)) closeJobs(); if (!management.value?.contains(event.target)) closeManagement(); }
function onJobsFocusOut(event) { if (!jobsContainer.value?.contains(event.relatedTarget)) closeJobs(); }
onMounted(() => document.addEventListener('click', outside));
onUnmounted(() => document.removeEventListener('click', outside));
</script>
<style scoped>
.navbar { position: sticky; top: 0; z-index: 100; padding: 10px max(var(--space-sm), env(safe-area-inset-right)) 0 max(var(--space-sm), env(safe-area-inset-left)); }
.navbar-inner { max-width: 1318px; margin: auto; padding: 8px 12px; display: flex; align-items: center; justify-content: space-between; gap: 24px; min-height: 64px; border-radius: 22px; }
.navbar-brand { display: flex; align-items: center; gap: 10px; color: var(--text-primary); font-weight: 650; font-size: 15px; white-space: nowrap; text-decoration: none; }
.navbar-brand i { color: var(--link-text); }
.navbar-links, .navbar-user { display: flex; align-items: center; gap: 4px; }
.navbar-links { margin-right: auto; }
.nav-link { display: flex; align-items: center; justify-content: center; gap: 7px; min-height: 44px; padding: 0 12px; border: 1px solid transparent; border-radius: 14px; background: none; color: var(--text-secondary); font: inherit; font-size: 13px; text-decoration: none; cursor: pointer; transition: background-color .16s ease, color .16s ease; }
.nav-link:hover { color: var(--text-primary); background: var(--glass-hover); text-decoration: none; }
.nav-link[aria-current=page], .management[open] summary, .nav-link[aria-expanded=true] { color: var(--link-text); background: var(--glass-active); border-color: var(--glass-edge); box-shadow: inset 0 1px 0 var(--glass-highlight); }
.nav-link[aria-current=page] { font-weight: 650; }
.nav-link:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
.jobs-count { min-width: 19px; text-align: center; background: var(--glass-active); color: var(--link-text); border-radius: 6px; padding: 0 4px; font-size: 11px; }
.active-jobs, .management { position: relative; }
.management summary { list-style: none; }
.management summary::-webkit-details-marker { display: none; }
.management-links, .active-jobs-dropdown { position: absolute; right: 0; top: calc(100% + 14px); width: 340px; max-width: calc(100vw - 48px); border: 1px solid var(--glass-edge); border-radius: 16px; background: var(--surface-white); color: var(--text-primary); box-shadow: var(--shadow-dropdown); padding: 6px; overflow: auto; max-height: min(70vh, 600px); }
.management-links { width: 210px; }
.appearance-setting { padding: 12px 10px 8px; margin-top: 6px; border-top: 1px solid var(--border-subtle); }
.appearance-setting label { display: block; margin-bottom: 6px; color: var(--text-secondary); font-size: 12px; font-weight: 650; }
.appearance-setting select { min-height: 44px; border-radius: 10px; }
.management-links a, .management-links button { display: block; padding: 12px 16px; font: inherit; font-size: 13px; background: none; border: 0; border-radius: 10px; color: var(--link-text); cursor: pointer; text-align: left; width: 100%; }
.active-jobs-header { padding: 10px 8px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); }
.active-jobs-header button { background: none; border: 0; color: var(--text-secondary); min-width: 36px; min-height: 36px; border-radius: 10px; cursor: pointer; }
.active-jobs-item { display: flex; flex-direction: column; gap: 3px; padding: 12px 10px; color: var(--text-primary); font-size: 13px; border-bottom: 1px solid var(--border-subtle); border-radius: 8px; }
.active-jobs-item small { color: var(--text-secondary); overflow-wrap: anywhere; }
.active-jobs-item:hover, .management-links a:hover, .management-links button:hover, .active-jobs-header button:hover { background: var(--surface-light); }
.active-jobs-empty, .active-jobs-footer { display: block; padding: 14px 10px; font-size: 13px; }
.active-jobs-empty { color: var(--text-secondary); }
.active-jobs-footer { color: var(--link-text); }
@media(max-width: 1000px) { .navbar-brand span { display: none; }.navbar-inner { gap: 12px; } }
@media(max-width: 650px) {
  .navbar { padding: 8px 8px 0; }
  .navbar-inner { display: grid; grid-template-columns: 1fr auto; gap: 4px 8px; padding: 6px 8px; border-radius: 20px; }
  .navbar-brand { padding: 8px 0; }.navbar-brand span { display: inline; font-size: 13px; }
  .navbar-user { grid-column: 2; grid-row: 1; gap: 2px; }
  .navbar-links { grid-row: 2; grid-column: 1/-1; margin: 0; justify-content: space-between; }
  .nav-link { padding: 0 8px; font-size: 12px; border-radius: 12px; }
  .navbar-user .nav-link { padding: 0 6px; }
  .active-jobs-dropdown { right: -35px; top: calc(100% + 8px); }.management-links { right: -85px; top: calc(100% + 8px); }
}
@media(max-width: 370px) { .navbar-brand span { display: none; }.navbar-links { gap: 0; }.navbar-links .nav-link { padding: 0 5px; font-size: 11px; } }
@media(max-height: 500px) { .navbar { position: relative; } }
@media(prefers-reduced-motion: reduce) { .nav-link { transition: none; } }
@media(forced-colors: active) {
  .nav-link[aria-current=page], .management[open] summary, .nav-link[aria-expanded=true] { border-color: Highlight; color: Highlight; }
  .nav-link:focus-visible { outline-color: Highlight; }
}
</style>
