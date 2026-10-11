<template>
  <section v-if="summary.nodes.length" class="storage-results" aria-label="Storage results">
    <h4>Home storage</h4>
    <p class="muted">Filesystem containing /home on each node.</p>
    <div class="table-scroll" role="region" aria-label="Home storage by node" tabindex="0">
      <table><thead><tr><th scope="col">Node</th><th scope="col">Mount</th><th scope="col">Used / total</th><th scope="col">Available</th><th scope="col">Use</th></tr></thead>
        <tbody><tr v-for="node in summary.nodes" :key="node.hostname">
          <th scope="row">{{ deviceName(node.hostname) }}</th><td><code>{{ node.home?.mountpoint || 'Unknown' }}</code></td>
          <template v-if="node.home?.accessible"><td>{{ storageSize(node.home.used_mb) }} / {{ storageSize(node.home.total_mb) }}</td><td>{{ storageSize(node.home.avail_mb) }}</td><td :class="{warning:storageIssue(node.home)}">{{ percent(node.home.use_pct) }}</td></template>
          <td v-else colspan="3" class="warning">{{ node.home ? storageState(node.home) : 'Home storage was not identified' }}</td>
        </tr></tbody>
      </table>
    </div>

    <template v-if="summary.additional.length">
      <h4>Additional mounts</h4>
      <div v-for="group in summary.additional" :key="group.key" class="mount-group">
        <details>
          <summary><span class="mount-name"><code v-if="group.shared">{{ group.source }}</code><span v-else>{{ deviceName(group.rows[0].hostname) }} · <code>{{ group.rows[0].mountpoint }}</code></span><small :class="{warning:group.issue}">{{ group.coverage }}</small></span><span class="reading" :class="{warning:group.reading && storageIssue(group.reading)}">{{ group.readingsDiffer ? 'Readings differ by node' : group.reading ? `${percent(group.reading.use_pct)} used · ${storageSize(group.reading.avail_mb)} available` : 'No capacity reading' }}</span></summary>
          <div class="table-scroll" role="region" :aria-label="`Node details for ${group.source || group.rows[0].mountpoint}`" tabindex="0">
            <table><thead><tr><th scope="col">Node / mount</th><th scope="col">Status</th><th scope="col">Used / total</th><th scope="col">Available</th></tr></thead><tbody>
              <tr v-for="(mount,index) in group.rows" :key="index"><th scope="row">{{ deviceName(mount.hostname) }}<small><code>{{ mount.mountpoint }}</code></small></th><td :class="{warning:storageIssue(mount)}">{{ storageState(mount) }}</td><template v-if="mount.accessible"><td>{{ storageSize(mount.used_mb) }} / {{ storageSize(mount.total_mb) }}<small>{{ percent(mount.use_pct) }} used</small></td><td>{{ storageSize(mount.avail_mb) }}</td></template><td v-else colspan="2">No capacity reading</td></tr>
            </tbody></table>
          </div>
        </details>
      </div>
    </template>

    <details class="all-details">
      <summary>All mount details<span v-if="summary.routineCount"> · {{ summary.routineCount }} boot or virtual mounts</span></summary>
      <section v-for="node in summary.nodes" :key="node.hostname" class="node-details">
        <h5>{{ deviceName(node.hostname) }} <span v-if="node.timestamp" class="muted">· {{ formatLongTime(node.timestamp) }}</span></h5>
        <div class="table-scroll" role="region" :aria-label="`All mounts on ${node.hostname}`" tabindex="0">
          <table><thead><tr><th scope="col">Mount / source</th><th scope="col">Status</th><th scope="col">Used / total</th><th scope="col">Available</th></tr></thead><tbody>
            <tr v-for="(mount,index) in node.mounts" :key="index">
              <th scope="row"><code>{{ mount.mountpoint }}</code><small v-if="mount.covers_home">Contains /home</small><small>{{ mount.source || mount.configured_source }} · {{ mount.fstype || mount.configured_fstype }}</small><small v-if="mount.configured_source && mount.source && mount.configured_source !== mount.source">Configured: {{ mount.configured_source }}</small><small v-if="mount.duplicates > 1">{{ mount.duplicates }} identical entries</small></th>
              <td :class="{warning:storageIssue(mount)}">{{ storageState(mount) }}<small v-if="mount.optional">Optional (nofail)</small><small v-if="mount.noauto">Manual (noauto)</small></td>
              <template v-if="mount.accessible"><td>{{ storageSize(mount.used_mb) }} / {{ storageSize(mount.total_mb) }}<small>{{ percent(mount.use_pct) }} used</small></td><td>{{ storageSize(mount.avail_mb) }}</td></template><td v-else colspan="2">{{ virtualMount(mount) && mount.mounted ? 'Capacity does not apply' : 'No capacity reading' }}</td>
            </tr>
          </tbody></table>
        </div>
      </section>
    </details>
    <p class="muted footnote">Shared mounts are grouped by source; capacity is never added across nodes. On-demand mounts are checked when already mounted.</p>
  </section>
</template>

<script setup>
import {computed} from 'vue';
import {formatLongTime} from '../utils/time.js';
import {storageSummary, storageSize, storageState, storageIssue, virtualMount, hasNumber} from '../utils/storage.js';
const props = defineProps({reports:{type:Array,default:()=>[]},devices:{type:Array,default:()=>[]}});
const summary = computed(() => storageSummary(props.reports));
const deviceName = hostname => props.devices.find(device => device.inventory_name === hostname)?.name || hostname;
const percent = value => hasNumber(value) ? `${value}%` : 'Unavailable';
</script>

<style scoped>
.storage-results{min-width:0;margin-top:20px}.storage-results h4{font-size:15px;margin:22px 0 8px}.storage-results h4:first-child{margin-top:0}.storage-results p{font-size:12px;line-height:1.6;margin:6px 0 12px}.muted,small{color:var(--text-secondary)}.warning{color:var(--status-warning-text)}.table-scroll{overflow-x:auto;max-width:100%;border:1px solid var(--border-subtle);border-radius:6px}.table-scroll:focus-visible,summary:focus-visible{outline:2px solid var(--focus-ring);outline-offset:2px}.storage-results table{width:100%;border-collapse:collapse;text-align:left;font-size:12px}.storage-results th,.storage-results td{padding:12px;vertical-align:top;border-bottom:1px solid var(--border-subtle)}thead{background:var(--surface-light)}thead th{color:var(--text-primary)}tbody th{text-transform:none;letter-spacing:normal;color:var(--text-primary)}th{font-weight:600}td{min-width:90px}small{display:block;font-size:11px;font-weight:400;margin-top:4px;overflow-wrap:anywhere}code{font-size:12px;overflow-wrap:anywhere}.storage-results tbody tr:last-child>*{border-bottom:0}.mount-group{border-bottom:1px solid var(--border-subtle)}summary{cursor:pointer;font-size:12px;line-height:1.6;padding:12px 0}.mount-group summary{display:flex;align-items:center;gap:16px}.mount-group summary:before{content:'▸';color:var(--text-secondary)}.mount-group details[open]>summary:before{content:'▾'}.mount-name{flex:1;min-width:0}.reading{flex-shrink:0}.mount-group .table-scroll{margin-bottom:12px}.all-details{margin-top:16px}.node-details{margin:16px 0}h5{font-size:12px;margin:0 0 8px}h5 span{font-weight:400}.footnote{margin-top:16px!important}@media(max-width:600px){.mount-group summary{flex-wrap:wrap;gap:4px 10px}.reading{flex-basis:100%;padding-left:20px}th,td{padding:10px}}
</style>
