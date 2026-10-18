import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { useDocumentVisibility, useIntervalFn } from '@vueuse/core';
import { getDevices, getJobOverview } from '../api.js';

// Independent observations: a failed resource never erases a successful one.
export const useDevicesStore = defineStore('devices', () => {
  const devices = ref([]), recentJobs = ref([]), activeJobs = ref([]), adverseJobs = ref([]);
  const activeJobCount = ref(null), lastUpdated = ref(null), jobsUpdated = ref(null), activeUpdated = ref(null), adverseUpdated = ref(null);
  const loading = ref(false), hasLoadedOnce = ref(false);
  const deviceError = ref(null), jobsError = ref(null);
  const activeError = computed(() => jobsError.value), adverseError = computed(() => jobsError.value);
  const error = computed(() => deviceError.value || jobsError.value || activeError.value || adverseError.value);
  let inFlight = null;

  async function refresh() {
    // Explicit refreshes share the request, so older responses cannot win.
    if (inFlight) return inFlight;
    loading.value = true;
    async function observe(fetchRows, apply, failure) {
      try { apply(await fetchRows()); failure.value = null; }
      catch (caught) { failure.value = caught; }
    }
    inFlight = Promise.all([
      observe(getDevices, rows => { devices.value = rows; lastUpdated.value = new Date().toISOString(); hasLoadedOnce.value = true; }, deviceError),
      observe(getJobOverview, snapshot => {
        recentJobs.value = snapshot.recent;
        activeJobs.value = snapshot.active;
        activeJobCount.value = snapshot.active_count;
        adverseJobs.value = snapshot.adverse;
        jobsUpdated.value = activeUpdated.value = adverseUpdated.value = new Date().toISOString();
      }, jobsError),
    ]).finally(() => { loading.value = false; inFlight = null; });
    return inFlight;
  }

  const visibility = useDocumentVisibility();
  const { pause, resume } = useIntervalFn(() => {
    if (visibility.value === 'visible') refresh();
  }, 30_000, { immediate: false });
  function start() { refresh(); resume(); }
  function stop() { pause(); }
  return { devices, recentJobs, activeJobs, adverseJobs, activeJobCount, lastUpdated, jobsUpdated, activeUpdated, adverseUpdated,
    loading, hasLoadedOnce, deviceError, jobsError, activeError, adverseError, error, refresh, start, stop };
});
