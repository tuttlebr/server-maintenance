import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { useDocumentVisibility, useIntervalFn } from "@vueuse/core";
import { getDevices, getJobs } from "../api.js";

// Shared fleet state. Poll only while the tab is visible so navigation stays
// current without multiplying requests across screens.
export const useDevicesStore = defineStore("devices", () => {
  const devices = ref([]);
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
        const [deviceRows, jobs] = await Promise.all([
          getDevices(),
          getJobs({ limit: 10 }).catch(() => []),
        ]);
        devices.value = deviceRows;
        recentJobs.value = jobs;
        lastUpdated.value = new Date();
        hasLoadedOnce.value = true;
      } catch (caught) {
        error.value = caught;
      } finally {
        loading.value = false;
        inFlight = null;
      }
    })();
    return inFlight;
  }

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
  function stop() { pause(); }

  const activeJobs = computed(() =>
    recentJobs.value.filter((job) => job.status === "running" || job.status === "pending")
  );

  return {
    devices, recentJobs, activeJobs, lastUpdated, loading, hasLoadedOnce,
    error, refresh, start, stop,
  };
});
