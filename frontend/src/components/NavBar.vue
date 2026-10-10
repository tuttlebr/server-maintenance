<template>
  <nav class="navbar" aria-label="Main navigation">
    <div class="navbar-inner">
      <router-link to="/" class="navbar-brand" aria-label="Fleet Manager operations"><i class="fas fa-layer-group" aria-hidden="true"></i><span>Fleet Manager</span></router-link>
      <div class="navbar-links"><router-link v-for="item in navigation" :key="item.to" :to="item.to" :aria-current="route.path === item.to || (item.to !== '/' && route.path.startsWith(item.to + '/')) ? 'page' : undefined" class="nav-link">{{ item.label }}</router-link></div>
      <div class="navbar-user">
        <details ref="management" class="management" @keydown.esc.prevent="closeManagement(true)">
          <summary class="nav-link">Manage</summary>
          <div class="management-links"><router-link to="/context" @click="closeManagement()">Knowledge sources</router-link><button type="button" @click="openHelp">Fleet Help</button></div>
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
.navbar { background: var(--surface-dark); position: sticky; top: 0; z-index: 100; }.navbar-inner { max-width: 1350px; margin: auto; padding: 0 var(--space-sm); display: flex; align-items: center; justify-content: space-between; gap: 24px; min-height: 64px; }.navbar-brand { display: flex; align-items: center; gap: 10px; color: #fff; font-weight: 650; font-size: 15px; white-space: nowrap; text-decoration: none; }.navbar-links, .navbar-user { display: flex; align-items: center; gap: 4px; }.navbar-links { margin-right: auto; }.nav-link { display: flex; align-items: center; gap: 7px; min-height: 64px; padding: 0 12px; border: 0; border-bottom: 3px solid transparent; background: none; color: #c3cbd6; font: inherit; font-size: 13px; text-decoration: none; cursor: pointer; }.nav-link:hover, .nav-link[aria-current=page] { color: #fff; text-decoration: none; }.nav-link[aria-current=page] { border-bottom-color: #91bcff; }.nav-link:focus-visible { outline: 2px solid #fff; outline-offset: -4px; }.jobs-count { min-width: 19px; text-align: center; background: #253d60; color: #d9e8ff; border-radius: 4px; padding: 0 4px; font-size: 11px; }.active-jobs, .management { position: relative; }.management summary { list-style: none; }.management summary::-webkit-details-marker { display: none; }.management[open] summary { color: #fff; border-bottom-color: #91bcff; }.management-links, .active-jobs-dropdown { position: absolute; right: 0; top: calc(100% - 5px); width: 340px; max-width: calc(100vw - 32px); border: 1px solid var(--border-subtle); border-radius: 6px; background: var(--surface-white); color: var(--text-primary); box-shadow: var(--shadow-dropdown); overflow: auto; max-height: min(70vh, 600px); }.management-links { width: 210px; }.management-links a, .management-links button { display: block; padding: 12px 16px; font: inherit; font-size: 13px; background: none; border: 0; color: var(--link-text); cursor: pointer; text-align: left; width: 100%; }.active-jobs-header { padding: 12px 14px; display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); }.active-jobs-header button { background: none; border: 0; color: var(--text-secondary); padding: 3px 6px; cursor: pointer; }.active-jobs-item { display: flex; flex-direction: column; gap: 3px; padding: 12px 14px; color: var(--text-primary); font-size: 13px; border-bottom: 1px solid var(--border-subtle); }.active-jobs-item small { color: var(--text-secondary); overflow-wrap: anywhere; }.active-jobs-item:hover, .management-links a:hover, .management-links button:hover { background: var(--surface-light); }.active-jobs-empty, .active-jobs-footer { display: block; padding: 14px; font-size: 13px; }.active-jobs-empty { color: var(--text-secondary); }.active-jobs-footer { color: var(--link-text); }
@media(max-width: 1000px) { .navbar-brand span { display: none; }.navbar-inner { gap: 12px; } }
@media(max-width: 650px) { .navbar-inner { display: grid; grid-template-columns: 1fr auto; gap: 0 8px; }.navbar-brand { padding: 10px 0; }.navbar-brand span { display: inline; font-size: 13px; }.navbar-user { grid-column: 2; grid-row: 1; }.navbar-links { grid-row: 2; grid-column: 1/-1; margin: 0; justify-content: space-between; }.nav-link { min-height: 42px; padding: 0 10px; font-size: 12px; }.navbar-user .nav-link { padding: 0 7px; }.active-jobs-dropdown { right: -35px; }.management-links { right: -85px; } }
@media(max-width: 370px) { .navbar-brand span { display: none; } }
@media(max-height: 500px) { .navbar { position: relative; } }
</style>
