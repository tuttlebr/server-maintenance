<template>
  <nav class="navbar" aria-label="Main navigation">
    <div class="navbar-inner">
      <router-link to="/" class="navbar-brand" aria-label="Fleet Manager overview">
        <span class="brand-mark" aria-hidden="true"><i class="fas fa-layer-group"></i></span>
        <span class="brand-text">Fleet Manager</span>
      </router-link>

      <div class="navbar-links">
        <router-link v-for="item in navigation" :key="item.to" :to="item.to" :aria-label="item.label" :title="item.label" class="nav-link">
          <i :class="['fas', item.icon]" aria-hidden="true"></i>
          <span>{{ item.label }}</span>
        </router-link>
      </div>

      <div class="navbar-user">
        <div class="active-jobs" :class="{ open: showJobs }">
          <button
            type="button"
            class="nav-link active-jobs-trigger"
            :aria-expanded="showJobs"
            aria-haspopup="true"
            :aria-label="store.activeJobCount == null ? 'Activity state unavailable' : `Active jobs: ${store.activeJobCount}`"
            @click.stop="showJobs = !showJobs"
          >
            <span class="active-jobs-icon">
              <i class="fas fa-bolt" aria-hidden="true"></i>
              <span v-if="store.activeJobCount" class="active-jobs-badge" aria-hidden="true">{{ store.activeJobCount }}</span>
            </span>
            <span>Active</span>
          </button>
          <div v-if="showJobs" class="active-jobs-dropdown" @click.stop>
            <div class="active-jobs-header">
              <strong>Active jobs</strong>
              <button class="active-jobs-close" type="button" aria-label="Close" @click="showJobs = false">&times;</button>
            </div>
            <router-link
              v-for="job in activeJobs"
              :key="job.job_id"
              :to="`/activity?job=${job.job_id}`"
              class="active-jobs-item"
              @click="showJobs = false"
            >
              <span class="dot dot-blue dot-pulse" aria-hidden="true"></span>
              <span class="active-jobs-item-text">
                <strong>{{ operationLabel(job.playbook) }}</strong>
                <small>{{ formatTargetList(job.target_devices) }} · {{ relativeTime(job.created_at) }}</small>
              </span>
            </router-link>
            <div v-if="store.error" class="active-jobs-empty">Activity could not be refreshed. {{ store.activeJobCount == null ? 'State is unavailable.' : 'Showing the last observation.' }}</div><div v-else-if="store.activeJobCount == null" class="active-jobs-empty">Loading activity…</div><div v-else-if="store.activeJobCount === 0" class="active-jobs-empty">No jobs running.</div>
            <router-link to="/activity" class="active-jobs-footer" @click="showJobs = false">
              View all activity
            </router-link>
          </div>
        </div>
        <button type="button" class="nav-link" aria-label="Sign out" @click="logout">
          <i class="fas fa-sign-out-alt" aria-hidden="true"></i><span>Sign Out</span>
        </button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { clearToken } from "../api.js";
import { useDevicesStore } from "../stores/devices.js";
import { relativeTime } from "../utils/time.js";
import { formatTargetList, operationLabel } from "../utils/devices.js";

const navigation = [
  { to: "/", label: "Overview", icon: "fa-chart-line" },
  { to: "/devices", label: "Devices", icon: "fa-server" },
  { to: "/operations", label: "Operations", icon: "fa-bolt" },
  { to: "/access", label: "Access", icon: "fa-users" },
  { to: "/activity", label: "Activity", icon: "fa-list-check" },
  { to: "/context", label: "Context", icon: "fa-book-open" },
];
const router = useRouter();
const store = useDevicesStore();
const showJobs = ref(false);
const activeJobs = computed(() => store.activeJobs);

function logout() { clearToken(); router.push("/login"); }
function closeOnOutsideClick() { showJobs.value = false; }
onMounted(() => document.addEventListener("click", closeOnOutsideClick));
onUnmounted(() => document.removeEventListener("click", closeOnOutsideClick));
</script>

<style scoped>
.navbar { background: var(--surface-dark); height: 64px; position: sticky; top: 0; z-index: 100; }
.navbar-inner { max-width: 1380px; margin: 0 auto; padding: 0 var(--space-sm); height: 100%; display: flex; align-items: center; justify-content: space-between; }
.navbar-brand { display: flex; align-items: center; gap: 10px; color: var(--text-on-dark); text-decoration: none; }
.brand-mark { width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center; color: white; background: var(--color-accent); }
.brand-text { font-size: 15px; font-weight: 650; letter-spacing: .1px; }
.navbar-links, .navbar-user { display: flex; align-items: center; height: 100%; }
.navbar-links { gap: 3px; }
.nav-link { display: flex; align-items: center; gap: 7px; padding: 0 13px; height: 64px; color: rgba(255,255,255,.72); border: 0; border-bottom: 2px solid transparent; background: none; font: inherit; font-size: 13px; text-decoration: none; cursor: pointer; }
.nav-link:hover, .nav-link:focus-visible, .nav-link.router-link-exact-active { color: #fff; }
.nav-link.router-link-exact-active { border-bottom-color: var(--color-accent); }
.nav-link:focus-visible { outline: 2px solid #fff; outline-offset: -4px; }
.active-jobs { position: relative; height: 100%; }
.active-jobs-icon { position: relative; display: inline-flex; }
.active-jobs-badge { position: absolute; top: -9px; right: -11px; min-width: 17px; height: 17px; padding: 0 4px; border-radius: 9px; display: grid; place-items: center; background: var(--color-danger); color: #fff; font-size: 10px; font-weight: 700; }
.active-jobs-dropdown { position: absolute; top: 56px; right: 0; width: 330px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--surface-white); color: var(--text-primary); box-shadow: var(--shadow-dropdown); overflow: hidden; }
.active-jobs-header { display: flex; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid var(--border-subtle); }
.active-jobs-close { border: 0; background: none; color: var(--text-secondary); cursor: pointer; font-size: 18px; }
.active-jobs-item { display: flex; gap: 10px; align-items: center; padding: 12px 14px; color: inherit; text-decoration: none; border-bottom: 1px solid var(--border-subtle); }
.active-jobs-item:hover { background: var(--surface-light); }
.active-jobs-item-text { display: flex; flex-direction: column; min-width: 0; }
.active-jobs-item-text small { color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.active-jobs-empty, .active-jobs-footer { display: block; padding: 14px; color: var(--text-secondary); }
.active-jobs-footer { color: var(--color-accent); text-decoration: none; border-top: 1px solid var(--border-subtle); }
@media (max-width: 900px) { .nav-link span { display: none; } .brand-text { display: none; } .navbar-links { flex: 1; justify-content: center; } }
</style>
