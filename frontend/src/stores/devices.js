import { defineStore } from "pinia";
import { ref } from "vue";
import { useDocumentVisibility, useIntervalFn } from "@vueuse/core";
import { getDevices, getJobs, getJobSummary } from "../api.js";

// Shared fleet state. Poll only while the tab is visible so navigation stays
// current without multiplying requests across screens.
export const useDevicesStore = defineStore("devices", () => {
  const devices = ref([]);
  const recentJobs = ref([]);
  const activeJobs = ref([]);
  const activeJobCount = ref(null);
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
        const [deviceRows, jobs, active, summary] = await Promise.all([
          getDevices(),
          getJobs({ limit: 10 }),
          getJobs({ status: "active", limit: 200 }),
          getJobSummary(),
        ]);
        devices.value = deviceRows;
        recentJobs.value = jobs;
        activeJobs.value = active;
        activeJobCount.value = summary.active_count;
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


  return {
    devices, recentJobs, activeJobs, activeJobCount, lastUpdated, loading, hasLoadedOnce,
    error, refresh, start, stop,
  };
});
