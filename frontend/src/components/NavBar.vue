<template>
  <nav class="navbar" aria-label="Main navigation">
    <div class="navbar-inner">
      <div class="navbar-brand">
        <svg class="nvidia-logo" viewBox="0 0 120 44" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="NVIDIA">
          <text x="0" y="32" fill="#76B900" font-family="NVIDIA Sans, sans-serif" font-weight="700" font-size="28">NVIDIA</text>
        </svg>
        <span class="brand-divider" aria-hidden="true"></span>
        <span class="brand-text">Fleet Manager</span>
      </div>

      <div class="navbar-links">
        <router-link to="/" class="nav-link" active-class="active" :class="{ active: $route.path === '/' }">
          <i class="fas fa-th-large" aria-hidden="true"></i>
          <span>Dashboard</span>
        </router-link>
        <router-link to="/users" class="nav-link" active-class="active">
          <i class="fas fa-users" aria-hidden="true"></i>
          <span>Users</span>
        </router-link>
        <router-link to="/drivers" class="nav-link" active-class="active">
          <i class="fas fa-microchip" aria-hidden="true"></i>
          <span>Drivers</span>
        </router-link>
        <router-link to="/networking" class="nav-link" active-class="active">
          <i class="fas fa-network-wired" aria-hidden="true"></i>
          <span>Networking</span>
        </router-link>
        <router-link to="/maintenance" class="nav-link" active-class="active">
          <i class="fas fa-wrench" aria-hidden="true"></i>
          <span>Maintenance</span>
        </router-link>
        <router-link to="/jobs" class="nav-link" active-class="active">
          <i class="fas fa-list-check" aria-hidden="true"></i>
          <span>Jobs</span>
        </router-link>
      </div>

      <div class="navbar-user">
        <!-- Active Jobs Tray -->
        <div class="active-jobs" :class="{ open: showJobs }">
          <button
            type="button"
            class="nav-link active-jobs-trigger"
            :aria-expanded="showJobs"
            aria-haspopup="true"
            :aria-label="`Active jobs: ${activeJobs.length}`"
            @click.stop="showJobs = !showJobs"
          >
            <span class="active-jobs-icon">
              <i class="fas fa-bolt" aria-hidden="true"></i>
              <span
                v-if="activeJobs.length"
                class="active-jobs-badge"
                aria-hidden="true"
              >{{ activeJobs.length }}</span>
            </span>
            <span>Active</span>
          </button>
          <div v-if="showJobs" class="active-jobs-dropdown" role="menu" @click.stop>
            <div class="active-jobs-header">
              <strong>Active jobs</strong>
              <button class="active-jobs-close" type="button" aria-label="Close" @click="showJobs = false">&times;</button>
            </div>
            <div v-if="activeJobs.length" class="active-jobs-list">
              <router-link
                v-for="job in activeJobs"
                :key="job.job_id"
                to="/jobs"
                class="active-jobs-item"
                @click="showJobs = false"
              >
                <span class="dot dot-blue dot-pulse" aria-hidden="true"></span>
                <span class="active-jobs-item-text">
                  <strong>{{ job.playbook }}</strong>
                  <small>{{ formatHostList(job.target_hosts) }} · {{ shortTime(job.created_at) }}</small>
                </span>
                <i class="fas fa-chevron-right" aria-hidden="true"></i>
              </router-link>
            </div>
            <div v-else class="active-jobs-empty">
              No jobs running.
            </div>
            <router-link to="/jobs" class="active-jobs-footer" @click="showJobs = false">
              <i class="fas fa-list-check" aria-hidden="true"></i> View all jobs
            </router-link>
          </div>
        </div>

        <button type="button" class="nav-link" aria-label="Sign out" @click="logout">
          <i class="fas fa-sign-out-alt" aria-hidden="true"></i>
          <span>Sign Out</span>
        </button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { clearToken } from "../api.js";
import { useHostsStore } from "../stores/hosts.js";
import { relativeTime } from "../utils/time.js";
import { formatHostList } from "../utils/hosts.js";

const router = useRouter();
const store = useHostsStore();
const showJobs = ref(false);
const activeJobs = computed(() => store.activeJobs);

function logout() {
  clearToken();
  router.push("/login");
}

const shortTime = relativeTime;

function closeOnOutsideClick() {
  showJobs.value = false;
}

onMounted(() => {
  document.addEventListener("click", closeOnOutsideClick);
});
onUnmounted(() => {
  document.removeEventListener("click", closeOnOutsideClick);
});
</script>

<style scoped>
.navbar {
  background-color: var(--surface-dark);
  height: 60px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.navbar-inner {
  max-width: 1350px;
  margin: 0 auto;
  padding: 0 var(--space-sm);
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.navbar-brand { display: flex; align-items: center; gap: 12px; }
.nvidia-logo { height: 24px; width: auto; }
.brand-divider { width: 1px; height: 24px; background-color: rgba(255, 255, 255, 0.2); }
.brand-text {
  color: var(--text-on-dark);
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.3px;
}

.navbar-links {
  display: flex;
  align-items: center;
  gap: 4px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  font-weight: 400;
  text-decoration: none;
  border-bottom: 2px solid transparent;
  transition: var(--transition-standard);
  background: none;
  border-top: none;
  border-left: none;
  border-right: none;
  cursor: pointer;
  font-family: var(--font-family);
  height: 60px;
}
.nav-link:hover, .nav-link:focus-visible {
  color: var(--text-on-dark);
  text-decoration: none;
  outline: none;
}
.nav-link:focus-visible { background: rgba(255, 255, 255, 0.1); }
.nav-link.active {
  color: var(--text-on-dark);
  border-bottom-color: var(--color-accent);
}
.nav-link i { font-size: 14px; }

.navbar-user {
  display: flex;
  align-items: center;
}

.active-jobs {
  position: relative;
  height: 100%;
}

.active-jobs-icon {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.active-jobs-badge {
  position: absolute;
  top: -6px;
  right: -10px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  background: var(--color-info);
  color: #fff;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 2px var(--surface-dark);
}

.active-jobs.open .nav-link.active-jobs-trigger,
.nav-link.active-jobs-trigger:hover {
  color: var(--text-on-dark);
}

.active-jobs-dropdown {
  position: absolute;
  top: calc(100% - 8px);
  right: 0;
  width: 320px;
  background: var(--surface-white);
  color: var(--text-on-light);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-dropdown);
  z-index: 200;
  overflow: hidden;
  animation: slideIn 0.18s ease-out;
}

.active-jobs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--surface-light);
  border-bottom: 1px solid var(--border-subtle);
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.active-jobs-close {
  appearance: none;
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 0 4px;
}

.active-jobs-list {
  max-height: 320px;
  overflow-y: auto;
}

.active-jobs-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-subtle);
  text-decoration: none;
  color: inherit;
  font-size: 13px;
  transition: var(--transition-standard);
}
.active-jobs-item:hover { background: var(--surface-light); }
.active-jobs-item:last-child { border-bottom: none; }

.active-jobs-item-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.active-jobs-item-text small {
  font-size: 11px;
  color: var(--text-secondary);
}

.active-jobs-empty {
  padding: 16px 14px;
  font-size: 13px;
  color: var(--text-secondary);
  text-align: center;
}

.active-jobs-footer {
  display: block;
  text-align: center;
  padding: 8px 14px;
  background: var(--surface-light);
  border-top: 1px solid var(--border-subtle);
  text-decoration: none;
  color: var(--color-info);
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.active-jobs-footer:hover { text-decoration: underline; }

@media (max-width: 1023px) {
  .nav-link span { display: none; }
  .nav-link i { font-size: 18px; }
  .brand-text { display: none; }
  .active-jobs-dropdown { width: 280px; }
}
</style>
