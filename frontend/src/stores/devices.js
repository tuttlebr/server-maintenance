import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { useDocumentVisibility, useIntervalFn } from '@vueuse/core';
import { getDevices, getJobs, getJobSummary } from '../api.js';

// Independent observations: a failed resource never erases a successful one.
export const useDevicesStore = defineStore('devices', () => {
  const devices = ref([]), recentJobs = ref([]), activeJobs = ref([]), adverseJobs = ref([]);
  const activeJobCount = ref(null), lastUpdated = ref(null), jobsUpdated = ref(null), activeUpdated = ref(null), adverseUpdated = ref(null);
  const loading = ref(false), hasLoadedOnce = ref(false);
  const deviceError = ref(null), jobsError = ref(null), activeError = ref(null), adverseError = ref(null);
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
      observe(() => getJobs({ limit: 50 }), rows => { recentJobs.value = rows; jobsUpdated.value = new Date().toISOString(); }, jobsError),
      observe(async () => {
        const [rows, summary] = await Promise.all([getJobs({ status: 'active', limit: 200 }), getJobSummary()]);
        return { rows, summary };
      }, ({ rows, summary }) => { activeJobs.value = rows; activeJobCount.value = summary.active_count; activeUpdated.value = new Date().toISOString(); }, activeError),
      observe(async () => {
        const [failed, partial, recovery] = await Promise.all([getJobs({ status: 'failed', limit: 5 }), getJobs({ status: 'partial', limit: 5 }), getJobs({ status: 'recovery_required', limit: 5 })]);
        return [...failed, ...partial, ...recovery].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
      }, rows => { adverseJobs.value = rows; adverseUpdated.value = new Date().toISOString(); }, adverseError),
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
