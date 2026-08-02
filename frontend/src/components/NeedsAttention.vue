<template>
  <section class="needs-attention" aria-label="Fleet needs attention">
    <h3 class="na-heading">Needs attention</h3>
    <div v-if="items.length" class="na-grid">
      <component
        :is="item.to ? 'router-link' : 'div'"
        v-for="item in items"
        :key="item.key"
        :to="item.to || undefined"
        :class="['callout', item.tone, item.to ? 'na-item-link' : '']"
      >
        <i :class="['fas', item.icon, 'callout-icon']" aria-hidden="true"></i>
        <div class="callout-body">
          <div class="callout-title">{{ item.title }}</div>
          <div class="na-subtitle">{{ item.subtitle }}</div>
        </div>
        <div v-if="item.to" class="callout-actions">
          <i class="fas fa-chevron-right" aria-hidden="true"></i>
        </div>
      </component>
    </div>
    <div v-else class="callout callout-success na-clear">
      <i class="fas fa-check-circle callout-icon" aria-hidden="true"></i>
      <div class="callout-body">
        <div class="callout-title">All clear</div>
        <div class="na-subtitle">No hosts need attention right now.</div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { ageInMs } from "../utils/time.js";
import { sortByHostname } from "../utils/hosts.js";

const props = defineProps({
  hosts: { type: Array, default: () => [] },
});

const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000; // 24h

const diskWarn = computed(() =>
  sortByHostname(
    props.hosts.filter(
      (h) => (h.disk_root_percent || 0) >= 85 || (h.disk_raid_percent || 0) >= 85,
    ),
  ),
);
const rebootList = computed(() => sortByHostname(props.hosts.filter((h) => h.reboot_required)));
const unknownList = computed(() => sortByHostname(props.hosts.filter((h) => h.status === "unknown")));
const offlineList = computed(() => sortByHostname(props.hosts.filter((h) => h.status === "offline")));
const staleList = computed(() =>
  sortByHostname(
    props.hosts.filter((h) => {
      if (h.status !== "online") return false;
      const age = ageInMs(h.last_seen);
      return age !== null && age > STALE_THRESHOLD_MS;
    }),
  ),
);

const items = computed(() => {
  const out = [];
  if (rebootList.value.length) {
    out.push({
      key: "reboot",
      icon: "fa-power-off",
      tone: "callout-warn",
      title: `${rebootList.value.length} host${rebootList.value.length === 1 ? "" : "s"} need a reboot`,
      subtitle: rebootList.value
        .slice(0, 3)
        .map((h) => h.hostname)
        .join(", ") + (rebootList.value.length > 3 ? ` and ${rebootList.value.length - 3} more` : ""),
      to: "/maintenance",
    });
  }
  if (diskWarn.value.length) {
    out.push({
      key: "disk",
      icon: "fa-hard-drive",
      tone: "callout-danger",
      title: `${diskWarn.value.length} host${diskWarn.value.length === 1 ? "" : "s"} low on disk`,
      subtitle: diskWarn.value
        .slice(0, 3)
        .map((h) => {
          const max = Math.max(h.disk_root_percent || 0, h.disk_raid_percent || 0);
          return `${h.hostname} (${max}%)`;
        })
        .join(", "),
      to: "/maintenance",
    });
  }
  if (offlineList.value.length) {
    out.push({
      key: "offline",
      icon: "fa-plug-circle-xmark",
      tone: "callout-danger",
      title: `${offlineList.value.length} host${offlineList.value.length === 1 ? "" : "s"} offline`,
      subtitle: offlineList.value
        .slice(0, 3)
        .map((h) => h.hostname)
        .join(", "),
    });
  }
  if (unknownList.value.length) {
    out.push({
      key: "unknown",
      icon: "fa-circle-question",
      tone: "callout-info",
      title: `${unknownList.value.length} host${unknownList.value.length === 1 ? "" : "s"} not yet scanned`,
      subtitle: "Click Scan Fleet to populate driver, disk, and network info.",
    });
  }
  if (staleList.value.length) {
    out.push({
      key: "stale",
      icon: "fa-clock-rotate-left",
      tone: "callout-info",
      title: `${staleList.value.length} host${staleList.value.length === 1 ? "" : "s"} not scanned in 24h+`,
      subtitle: "Last-seen data may be out of date.",
    });
  }
  return out;
});
</script>

<style scoped>
.needs-attention {
  margin-top: var(--space-md);
  margin-bottom: var(--space-md);
}

.na-heading {
  margin: 0 0 var(--space-xs);
  font-size: 15px;
  font-weight: 600;
}

.na-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-xs);
}

.na-subtitle {
  color: var(--text-secondary);
  font-size: 12px;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.na-item-link {
  text-decoration: none;
  color: inherit;
  transition: var(--transition-standard);
}
.na-item-link:hover {
  filter: brightness(0.97);
  text-decoration: none;
}
.na-item-link:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.na-clear { max-width: 420px; }
</style>
