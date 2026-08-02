import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { useDocumentVisibility, useIntervalFn } from "@vueuse/core";
import { getHosts, getJobs } from "../api.js";

// Shared store for fleet state. Polls /hosts on a 30s cadence when the tab is
// visible; pauses on background tabs. Multiple views subscribe and reflect the
// same data so the UI doesn't show stale info across navigations.
export const useHostsStore = defineStore("hosts", () => {
  const hosts = ref([]);
  const recentJobs = ref([]);
  const lastUpdated = ref(null);
  const loading = ref(false);
  const hasLoadedOnce = ref(false);
  const error = ref(null);

  let inFlight = null;

  async function refresh({ force = false } = {}) {
    if (inFlight && !force) return inFlight;
    loading.value = true;
    error.value = null;
    inFlight = (async () => {
      try {
        const [h, j] = await Promise.all([
          getHosts(),
          getJobs({ limit: 10 }).catch(() => []),
        ]);
        hosts.value = h;
        recentJobs.value = j;
        lastUpdated.value = new Date();
        hasLoadedOnce.value = true;
      } catch (e) {
        error.value = e;
      } finally {
        loading.value = false;
        inFlight = null;
      }
    })();
    return inFlight;
  }

  // Visibility-gated polling
  const visibility = useDocumentVisibility();
  const { pause, resume } = useIntervalFn(
    () => {
      if (visibility.value === "visible") refresh();
    },
    30_000,
    { immediate: false }
  );

  function start() {
    if (!hasLoadedOnce.value) refresh();
    resume();
  }
  function stop() {
    pause();
  }

  // Active (running/pending) jobs — surfaced in NavBar tray
  const activeJobs = computed(() =>
    recentJobs.value.filter((j) => j.status === "running" || j.status === "pending")
  );

  return {
    hosts,
    recentJobs,
    activeJobs,
    lastUpdated,
    loading,
    hasLoadedOnce,
    error,
    refresh,
    start,
    stop,
  };
});
