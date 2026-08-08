<template>
  <div>
    <div class="page-header">
      <h2>System Maintenance</h2>
      <button class="btn btn-ghost btn-sm" aria-label="Refresh maintenance data" @click="load">
        <i class="fas fa-sync-alt" aria-hidden="true"></i> Refresh
      </button>
    </div>
    <PageIntro>
      Routine fleet upkeep for the common cases first: GPU usage, disk cleanup owners, reboots, Docker cleanup, and health checks. Full system maintenance, provisioning, firmware, drain/resume, MIG, and docs indexing stay in the advanced section.
    </PageIntro>

    <nav class="section-nav" aria-label="Maintenance sections">
      <a
        v-for="s in sections"
        :key="s.id"
        :href="`#${s.id}`"
        :class="['section-nav-link', { active: activeSection === s.id }]"
        @click.prevent="goToSection(s.id)"
      >
        <i :class="['fas', s.icon]" aria-hidden="true"></i>
        <span>{{ s.label }}</span>
      </a>
    </nav>

    <!-- Target Selector -->
    <section id="targets" ref="targetsRef" class="card section-card target-card">
      <div class="card-body">
        <div class="target-card-main">
          <div>
            <h4 class="section-heading">
              <i class="fas fa-crosshairs section-icon" aria-hidden="true"></i> Maintenance Targets
            </h4>
            <p class="section-intro target-intro">
              Host-scoped actions use this target. Selected hosts can be one machine or any subset.
            </p>
          </div>
          <div class="target-summary-panel" aria-live="polite">
            <span class="target-summary-label">Current target</span>
            <span class="target-summary-value">{{ targetSummary }}</span>
          </div>
        </div>
        <div class="target-control-row">
          <div class="target-mode" role="group" aria-label="Maintenance target mode">
            <button
              type="button"
              :class="['btn', 'btn-sm', targetMode === 'all' ? 'btn-primary' : 'btn-ghost']"
              @click="setTargetMode('all')"
            >
              <i class="fas fa-server" aria-hidden="true"></i> All Hosts
            </button>
            <button
              type="button"
              :class="['btn', 'btn-sm', targetMode === 'selected' ? 'btn-primary' : 'btn-ghost']"
              @click="setTargetMode('selected')"
            >
              <i class="fas fa-check-square" aria-hidden="true"></i> Selected Hosts
            </button>
          </div>
          <div v-if="targetMode === 'selected'" class="target-select-tools">
            <button class="btn btn-ghost btn-sm" type="button" @click="selectAllTargets">
              <i class="fas fa-check-double" aria-hidden="true"></i> All
            </button>
            <button class="btn btn-ghost btn-sm" type="button" @click="selectGpuTargets">
              <i class="fas fa-microchip" aria-hidden="true"></i> GPU
            </button>
            <button class="btn btn-ghost btn-sm" type="button" @click="selectWorkstationTargets">
              <i class="fas fa-server" aria-hidden="true"></i> Workstations
            </button>
            <button class="btn btn-ghost btn-sm" type="button" :disabled="!selectedTargets.length" @click="clearTargetSelection">
              <i class="fas fa-times" aria-hidden="true"></i> Clear
            </button>
          </div>
        </div>
        <div v-if="targetMode === 'selected'" class="target-select-panel">
          <div class="checkbox-group target-checkboxes">
            <label class="checkbox-label target-checkbox" v-for="h in allHosts" :key="h.hostname">
              <input type="checkbox" :value="h.hostname" v-model="selectedTargets" />
              <span class="target-host-name">{{ h.hostname }}</span>
              <span :class="['badge', getMachineType(h.machine_type).badge]">
                {{ getMachineType(h.machine_type).short }}
              </span>
            </label>
          </div>
          <p v-if="!selectedTargets.length" class="target-warning">
            Select at least one host to run targeted maintenance actions.
          </p>
        </div>
      </div>
    </section>

    <!-- Disk Usage -->
    <section id="disk" ref="diskRef" class="card section-card">
      <div class="card-body">
        <h4 style="margin-bottom: var(--space-xs)"><i class="fas fa-hdd section-icon" aria-hidden="true"></i> Disk Usage</h4>
        <p class="section-intro">Root and the busiest non-root mounted filesystem per host. Bars turn orange at 75% and red at 90%.</p>
        <div v-if="diskUsage.length">
          <div v-for="d in diskUsage" :key="d.hostname" class="disk-host-row">
            <div class="disk-host-name">
              <router-link :to="`/hosts/${d.hostname}`">{{ d.hostname }}</router-link>
            </div>
            <div class="disk-bars">
              <div class="disk-bar-group">
                <span class="disk-bar-label">Root</span>
                <div class="progress-bar" style="flex: 1">
                  <div class="progress-fill" :class="diskClass(d.disk_root_percent)" :style="{ width: (d.disk_root_percent || 0) + '%' }"></div>
                </div>
                <span class="disk-bar-pct">{{ d.disk_root_percent || 0 }}%</span>
              </div>
              <div class="disk-bar-group">
                <span class="disk-bar-label">Other max <InfoTooltip :text="GLOSSARY.storage" /></span>
                <div class="progress-bar" style="flex: 1">
                  <div class="progress-fill" :class="diskClass(d.disk_raid_percent)" :style="{ width: (d.disk_raid_percent || 0) + '%' }"></div>
                </div>
                <span class="disk-bar-pct">{{ d.disk_raid_percent || 0 }}%</span>
              </div>
            </div>
          </div>
        </div>
        <p v-else style="color: var(--text-secondary)">No host data available</p>
      </div>
    </section>

    <!-- Reboot Required -->
    <section id="reboot" ref="rebootRef" class="card section-card">
      <div class="card-body">
        <div class="flex items-center justify-between" style="margin-bottom: var(--space-sm)">
          <h4>
            <i class="fas fa-power-off section-icon" aria-hidden="true"></i>
            Reboot Required
            <span v-if="rebootHosts_.length" class="badge badge-red" style="margin-left: 8px">{{ rebootHosts_.length }}</span>
          </h4>
          <button
            v-if="rebootHosts_.length"
            class="btn btn-danger btn-sm"
            @click="openRebootAll"
          >
            <i class="fas fa-power-off" aria-hidden="true"></i> Reboot All ({{ rebootHosts_.length }})
          </button>
        </div>
        <p class="section-intro">Hosts flagged by Linux as needing a reboot — usually after a kernel update or driver upgrade.</p>

        <JobInlineStatus
          v-for="(id, idx) in rebootJobIds"
          :key="id"
          :job-id="id"
          label="Reboot"
          @done="onRebootDone(id)"
          @failed="onRebootFailed(id)"
          @dismiss="rebootJobIds.splice(idx, 1)"
        />
        <div v-if="rebootHosts_.length">
          <div class="table-wrapper" style="box-shadow: none">
            <table class="table-reflow">
              <thead>
                <tr>
                  <th>Hostname</th>
                  <th>Type</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="h in rebootHosts_" :key="h.hostname">
                  <td data-label="Hostname">
                    <router-link :to="`/hosts/${h.hostname}`" style="font-weight: 500">{{ h.hostname }}</router-link>
                  </td>
                  <td data-label="Type">
                    <span :class="['badge', getMachineType(h.machine_type).badge]">
                      {{ getMachineType(h.machine_type).short }}
                    </span>
                  </td>
                  <td data-label="Action">
                    <button class="btn btn-ghost btn-sm" style="color: var(--color-danger)" @click="askRebootSingle(h.hostname)">
                      <i class="fas fa-power-off" aria-hidden="true"></i> Reboot
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <p v-else style="color: var(--text-secondary); font-size: 14px">
          <i class="fas fa-check-circle" aria-hidden="true" style="color: var(--color-success)"></i> No hosts require a reboot
        </p>

        <button
          v-if="rebootHosts_.length"
          type="button"
          class="ask-helper"
          @click="askHelpChat('Why does a host need a reboot, and is it safe to do it during work hours?')"
        >
          <i class="fas fa-circle-question" aria-hidden="true"></i>
          Ask DGX Help: why does a host need a reboot?
        </button>

        <div class="separator"></div>
        <h5 style="margin-bottom: var(--space-xs); color: var(--text-secondary)">Targeted Reboot</h5>
        <div class="flex gap-xs items-center flex-wrap">
          <span class="badge badge-outline">Target: {{ actionTargetLabel('reboot') }}</span>
          <button
            class="btn btn-danger btn-sm"
            :disabled="!canRunHostAction('reboot')"
            :title="actionDisabledTitle('reboot')"
            @click="askTargetedReboot"
          >
            <i class="fas fa-power-off" aria-hidden="true"></i> Reboot Targets
          </button>
        </div>
      </div>
    </section>

    <!-- Reboot dialogs -->
    <ConfirmDialog
      :visible="rebootAllOpen"
      title="Reboot all flagged hosts"
      :confirm-text="`Reboot ${rebootHosts_.length} host${rebootHosts_.length !== 1 ? 's' : ''}`"
      :danger-mode="true"
      danger-label="High-blast-radius action"
      :require-text="rebootAllConfirmWord"
      @confirm="rebootAll"
      @cancel="rebootAllOpen = false"
    >
      <p>Each host will reboot one at a time, waiting for the previous to come back online before proceeding. Estimated duration:
        <strong>≈ {{ Math.max(2, rebootHosts_.length * 3) }} minutes</strong>.
      </p>
      <p style="margin-top: var(--space-xs); font-size: 13px; color: var(--text-secondary)">Hosts to be rebooted:</p>
      <ul class="reboot-host-list">
        <li v-for="h in rebootHosts_" :key="h.hostname">
          <span :class="['badge', getMachineType(h.machine_type).badge]" style="font-size: 10px; margin-right: 6px">
            {{ getMachineType(h.machine_type).short }}
          </span>
          <code>{{ h.hostname }}</code>
        </li>
      </ul>
    </ConfirmDialog>

    <ConfirmDialog
      :visible="confirmSingleReboot.visible"
      :title="`Reboot ${confirmSingleReboot.hostname}`"
      :message="`This will immediately reboot ${confirmSingleReboot.hostname} and wait for it to come back online.`"
      confirm-text="Reboot host"
      :danger-mode="true"
      @confirm="doSingleReboot"
      @cancel="confirmSingleReboot.visible = false"
    />

    <ConfirmDialog
      :visible="targetedRebootConfirm.visible"
      :title="`Reboot ${targetedRebootConfirm.label}`"
      :message="`This force-reboots ${targetedRebootConfirm.label}, even if Linux has not reported a reboot requirement.`"
      confirm-text="Reboot targets"
      :danger-mode="true"
      :require-text="targetedRebootConfirm.requireText"
      @confirm="doTargetedReboot"
      @cancel="targetedRebootConfirm.visible = false"
    />

    <!-- Storage Analysis + GPU Usage — 2-col row when collapsed, full-width when populated -->
    <div class="grid section-row">
    <section id="storage" ref="storageRef" :class="['card', 'section-card', storageWide ? 'col-12' : 'col-6 col-md-12']">
      <div class="card-body">
        <div class="flex items-center justify-between" style="margin-bottom: var(--space-sm)">
          <h4><i class="fas fa-chart-pie section-icon" aria-hidden="true"></i> Storage Analysis</h4>
          <button
            class="btn btn-primary btn-sm"
            :disabled="analysisRunning || !canRunHostAction('storage')"
            :title="actionDisabledTitle('storage')"
            @click="runAnalysis"
          >
            <i :class="['fas', analysisRunning ? 'fa-spinner fa-spin' : 'fa-search']" aria-hidden="true"></i>
            {{ analysisRunning ? 'Analyzing…' : 'Analyze Storage' }}
          </button>
        </div>
        <p class="target-line">Target: {{ actionTargetLabel('storage') }}</p>
        <p class="section-intro">Deep scan of mounted local, RAID, NFS, SMB, and other capacity-backed filesystems. Each filesystem appears once, even when it has multiple mount paths. Click a row to see the largest entries.</p>

        <JobInlineStatus
          v-if="storageJobId"
          :job-id="storageJobId"
          label="Storage analysis"
          @done="onStorageDone"
          @failed="onStorageFailed"
          @dismiss="storageJobId = ''"
        />

        <div v-if="storageData.length">
          <div v-for="report in storageData" :key="report.hostname" class="sa-host">
            <h5 style="margin-bottom: var(--space-xs)">
              <router-link :to="`/hosts/${report.hostname}`">{{ report.hostname }}</router-link>
            </h5>

            <div class="sa-table">
              <div v-for="m in (report.mounts || [])" :key="m.mountpoint" class="sa-row-wrap">
                <div
                  class="sa-row"
                  role="button"
                  tabindex="0"
                  :aria-expanded="isMountExpanded(report.hostname, m.mountpoint)"
                  @click="toggleMount(report.hostname, m.mountpoint)"
                  @keydown.enter.prevent="toggleMount(report.hostname, m.mountpoint)"
                  @keydown.space.prevent="toggleMount(report.hostname, m.mountpoint)"
                >
                  <span class="sa-label">
                    {{ m.mountpoint }}
                    <span :class="['badge', mountBadgeClass(m.type)]" style="font-size: 10px; margin-left: 4px">{{ m.type }}</span>
                  </span>
                  <div class="progress-bar sa-bar">
                    <div class="progress-fill" :class="diskClass(m.use_pct)" :style="{ width: m.use_pct + '%' }"></div>
                  </div>
                  <span class="sa-pct" :class="diskClass(m.use_pct)">{{ m.use_pct }}%</span>
                  <span class="sa-sizes">{{ formatSize(m.used_mb) }} / {{ formatSize(m.total_mb) }}</span>
                  <i v-if="m.entries && m.entries.length" class="fas fa-chevron-down sa-expand-icon" :class="{ rotated: isMountExpanded(report.hostname, m.mountpoint) }" aria-hidden="true"></i>
                </div>
                <div v-if="isMountExpanded(report.hostname, m.mountpoint) && m.entries && m.entries.length" class="sa-details">
                  <div v-for="entry in m.entries.slice(0, 10)" :key="entry.name" class="storage-row">
                    <span class="storage-name">{{ entry.name }}</span>
                    <div class="progress-bar" style="flex: 1; margin: 0 8px">
                      <div class="progress-fill" :class="barColor(entry.size_mb, m.total_mb)" :style="{ width: pct(entry.size_mb, m.total_mb) + '%' }"></div>
                    </div>
                    <span class="storage-size">{{ formatSize(entry.size_mb) }}</span>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
        <p v-else style="color: var(--text-secondary); font-size: 14px">
          Click "Analyze Storage" to discover and scan mounted storage across the fleet.
        </p>
      </div>
    </section>

    <!-- GPU Usage -->
    <section id="gpu" ref="gpuRef" :class="['card', 'section-card', gpuWide ? 'col-12' : 'col-6 col-md-12']">
      <div class="card-body">
        <div class="flex items-center justify-between" style="margin-bottom: var(--space-sm)">
          <h4><i class="fas fa-microchip section-icon" aria-hidden="true"></i> GPU Usage</h4>
          <button
            class="btn btn-primary btn-sm"
            :disabled="gpuRunning || !canRunHostAction('gpu')"
            :title="actionDisabledTitle('gpu')"
            @click="runGpuAnalysis"
          >
            <i :class="['fas', gpuRunning ? 'fa-spinner fa-spin' : 'fa-search']" aria-hidden="true"></i>
            {{ gpuRunning ? 'Scanning…' : 'Scan GPU Usage' }}
          </button>
        </div>
        <p class="target-line">Target: {{ actionTargetLabel('gpu') }}</p>
        <p class="section-intro">Per-GPU memory and utilization, plus the user and process holding each GPU. Free / idle / active counts at a glance.</p>

        <JobInlineStatus
          v-if="gpuJobId"
          :job-id="gpuJobId"
          label="GPU usage scan"
          @done="onGpuDone"
          @failed="onGpuFailed"
          @dismiss="gpuJobId = ''"
        />

        <div v-if="gpuData.length">
          <div v-for="report in gpuData" :key="report.hostname" style="margin-bottom: var(--space-md)">
            <h5 style="margin-bottom: var(--space-xs)">
              <router-link :to="`/hosts/${report.hostname}`">{{ report.hostname }}</router-link>
              <span v-if="report.memory_architecture === 'UMA'" class="badge badge-blue" style="font-size: 10px; margin-left: 6px">UMA</span>
              <span style="font-weight: 400; color: var(--text-secondary); margin-left: 8px; font-size: 12px">
                {{ report.total_gpus }} GPUs:
                <span style="color: var(--color-success)">{{ report.free_gpus }} free</span>
                <span v-if="report.idle_gpus"> &middot; <span style="color: var(--color-warning)">{{ report.idle_gpus }} idle</span></span>
                &middot; <span style="color: var(--color-info)">{{ report.active_gpus }} active</span>
              </span>
            </h5>
            <div v-if="report.memory_architecture === 'UMA'" class="callout callout-info gpu-note">
              <i class="fas fa-memory callout-icon" aria-hidden="true"></i>
              <div class="callout-body">
                <div class="callout-title">Unified memory platform</div>
                <div class="gpu-note-text">
                  GPU framebuffer memory can be reported as unsupported. System available:
                  {{ formatSize(report.system_memory?.mem_available_mb) }}
                  <span v-if="report.system_memory?.swap_free_mb"> · swap free {{ formatSize(report.system_memory.swap_free_mb) }}</span>
                </div>
              </div>
            </div>

            <div v-if="report.user_summary && report.user_summary.length"
                 style="margin-bottom: var(--space-sm); display: flex; gap: 8px; flex-wrap: wrap">
              <span v-for="u in report.user_summary" :key="u.user" class="badge badge-outline" style="font-size: 12px">
                {{ u.user }}: {{ u.gpu_count }} GPU{{ u.gpu_count !== 1 ? 's' : '' }}
                ({{ formatSize(u.total_memory_mb) }})
              </span>
            </div>

            <div class="table-wrapper" style="box-shadow: none">
              <table>
                <thead>
                  <tr>
                    <th style="width: 50px">GPU</th>
                    <th>Memory</th>
                    <th style="width: 55px">Util</th>
                    <th style="width: 100px">Status</th>
                    <th>User</th>
                    <th style="width: 90px">Source</th>
                    <th>Process / Container</th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="gpu in report.gpus" :key="gpu.index">
                    <tr v-if="!gpu.processes || gpu.processes.length === 0">
                      <td style="font-weight: 600">#{{ gpu.index }}</td>
                      <td>
                        <div class="progress-bar" style="width: 100px; display: inline-block; vertical-align: middle">
                          <div class="progress-fill good" :style="{ width: gpuMemPct(gpu) + '%' }"></div>
                        </div>
                        <span style="font-size: 11px; margin-left: 4px; color: var(--text-secondary)">
                          {{ gpuMemoryLabel(gpu, report) }}
                        </span>
                      </td>
                      <td>{{ gpu.utilization_pct }}%</td>
                      <td><span :class="['badge', gpuStatusClass(gpu.status)]">{{ gpuStatusLabel(gpu.status) }}</span></td>
                      <td colspan="3" style="color: var(--text-secondary); font-style: italic; font-size: 13px">No processes</td>
                    </tr>
                    <tr v-for="(proc, pi) in gpu.processes" :key="`${gpu.index}-${proc.pid}`">
                      <td v-if="pi === 0" :rowspan="gpu.processes.length" style="font-weight: 600">#{{ gpu.index }}</td>
                      <td v-if="pi === 0" :rowspan="gpu.processes.length">
                        <div class="progress-bar" style="width: 100px; display: inline-block; vertical-align: middle">
                          <div class="progress-fill"
                               :class="gpuMemPct(gpu) >= 90 ? 'danger' : gpuMemPct(gpu) >= 70 ? 'warn' : 'good'"
                               :style="{ width: gpuMemPct(gpu) + '%' }"></div>
                        </div>
                        <span style="font-size: 11px; margin-left: 4px; color: var(--text-secondary)">
                          {{ gpuMemoryLabel(gpu, report) }}
                        </span>
                      </td>
                      <td v-if="pi === 0" :rowspan="gpu.processes.length">{{ gpu.utilization_pct }}%</td>
                      <td v-if="pi === 0" :rowspan="gpu.processes.length">
                        <span :class="['badge', gpuStatusClass(gpu.status)]">{{ gpuStatusLabel(gpu.status) }}</span>
                      </td>
                      <td style="font-weight: 500">{{ proc.user }}</td>
                      <td>
                        <span :class="['badge', proc.source === 'docker' ? 'badge-blue' : proc.source === 'kubernetes' ? 'badge-orange' : 'badge-outline']"
                              style="font-size: 11px">
                          {{ proc.source }}
                        </span>
                      </td>
                      <td style="font-size: 13px">
                        <span>{{ proc.process_name }}</span>
                        <span v-if="proc.container_name" style="color: var(--text-secondary)"> &middot; {{ proc.container_name }}</span>
                        <span v-if="proc.pod_name" style="color: var(--text-secondary)"> &middot; {{ proc.namespace }}/{{ proc.pod_name }}</span>
                        <span style="color: var(--text-secondary); font-size: 11px; margin-left: 4px">({{ formatSize(proc.gpu_memory_mb) }})</span>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <p v-else style="color: var(--text-secondary); font-size: 14px">
          Click "Scan GPU Usage" to check who is using GPUs across the fleet.
        </p>
      </div>
    </section>
    </div>

    <!-- Actions -->
    <section id="actions" ref="actionsRef" class="grid section-card-grid">
      <div class="col-12">
        <div class="maintenance-group-heading">
          <div>
            <h4>Quick Maintenance</h4>
            <p>Low-surprise actions operators use most often for this fleet.</p>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-6 col-sm-12">
        <div class="card maintenance-card">
          <div class="card-body">
            <div class="maintenance-card-header">
              <h4><i class="fas fa-broom section-icon" aria-hidden="true"></i> Docker Cleanup</h4>
              <span class="maintenance-impact impact-change">Cleanup</span>
            </div>
            <p class="maintenance-card-copy">
              Prune dangling Docker images, networks, and unused containerd images.
            </p>
            <div class="target-chip">
              <i class="fas fa-crosshairs" aria-hidden="true"></i>
              <span>{{ actionTargetLabel('docker') }}</span>
            </div>
            <div class="maintenance-actions">
              <button
                class="btn btn-primary btn-sm"
                :disabled="!canRunHostAction('docker')"
                :title="actionDisabledTitle('docker')"
                @click="askDockerCleanup"
              >
                <i class="fas fa-broom" aria-hidden="true"></i> Clean Targets
              </button>
            </div>
            <div class="job-stack">
              <JobInlineStatus
                v-for="(id, idx) in dockerJobIds"
                :key="id"
                :job-id="id"
                label="Docker cleanup"
                @dismiss="dockerJobIds.splice(idx, 1)"
              />
            </div>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-6 col-sm-12">
        <div class="card maintenance-card">
          <div class="card-body">
            <div class="maintenance-card-header">
              <h4><i class="fas fa-clipboard-check section-icon" aria-hidden="true"></i> Preflight and Diagnostics</h4>
              <span class="maintenance-impact impact-read">Read-only</span>
            </div>
            <p class="maintenance-card-copy">
              Check maintenance blockers or collect deeper host health output before disruptive work.
            </p>
            <div class="target-chip">
              <i class="fas fa-crosshairs" aria-hidden="true"></i>
              <span>{{ actionTargetLabel('preflight') }}</span>
            </div>
            <div class="maintenance-actions">
              <button
                class="btn btn-primary btn-sm"
                type="button"
                :disabled="!canRunHostAction('preflight')"
                :title="actionDisabledTitle('preflight')"
                @click="runPreflight"
              >
                <i class="fas fa-clipboard-check" aria-hidden="true"></i> Preflight
              </button>
              <button
                class="btn btn-ghost btn-sm"
                type="button"
                :disabled="!canRunHostAction('health')"
                :title="actionDisabledTitle('health')"
                @click="runHealth"
              >
                <i class="fas fa-stethoscope" aria-hidden="true"></i> Diagnostics
              </button>
            </div>
            <div class="job-stack">
              <JobInlineStatus
                v-for="(id, idx) in preflightJobIds"
                :key="id"
                :job-id="id"
                label="Preflight check"
                @dismiss="preflightJobIds.splice(idx, 1)"
              />
              <JobInlineStatus
                v-for="(id, idx) in healthJobIds"
                :key="id"
                :job-id="id"
                label="Health diagnostics"
                @dismiss="healthJobIds.splice(idx, 1)"
              />
            </div>
          </div>
        </div>
      </div>
    </section>

    <section id="advanced" ref="advancedRef" class="grid section-card-grid">
      <div class="col-12">
        <div class="maintenance-group-heading advanced">
          <div>
            <h4>Advanced Maintenance</h4>
            <p>Broad system changes, provisioning, firmware, Kubernetes drain, and GPU mode changes.</p>
          </div>
        </div>
      </div>
      <div class="col-12">
        <div class="card maintenance-card">
          <div class="card-body">
            <div class="maintenance-card-header">
              <h4><i class="fas fa-screwdriver-wrench section-icon" aria-hidden="true"></i> Full System Maintenance</h4>
              <span class="maintenance-impact impact-danger">Disruptive</span>
            </div>
            <p class="maintenance-card-copy">
              Run package and firmware updates, mount remediation, kernel and container cleanup, storage checks, and zombie-process remediation. Hosts can reboot automatically.
            </p>
            <div class="target-chip">
              <i class="fas fa-crosshairs" aria-hidden="true"></i>
              <span>{{ actionTargetLabel('system') }}</span>
            </div>
            <div class="maintenance-actions">
              <button
                class="btn btn-danger btn-sm"
                type="button"
                :disabled="!canRunHostAction('system')"
                :title="actionDisabledTitle('system')"
                @click="confirmAdvanced('system')"
              >
                <i class="fas fa-screwdriver-wrench" aria-hidden="true"></i> Run Maintenance
              </button>
            </div>
            <div class="job-stack">
              <JobInlineStatus
                v-for="(id, idx) in systemMaintenanceJobIds"
                :key="id"
                :job-id="id"
                label="Full system maintenance"
                @dismiss="systemMaintenanceJobIds.splice(idx, 1)"
              />
            </div>
          </div>
        </div>
      </div>
      <div class="col-4 col-md-6 col-sm-12">
        <div class="card maintenance-card">
          <div class="card-body">
            <div class="maintenance-card-header">
              <h4><i class="fas fa-tools section-icon" aria-hidden="true"></i> Bootstrap and Firmware</h4>
              <span class="maintenance-impact impact-danger">Provision</span>
            </div>
            <p class="maintenance-card-copy">
              Onboard hosts, inventory firmware, or apply firmware updates as a separate maintenance action.
            </p>
            <div class="target-chip">
              <i class="fas fa-crosshairs" aria-hidden="true"></i>
              <span>{{ actionTargetLabel('bootstrap') }}</span>
              <span v-if="firmwareTargetNote"> · Firmware: {{ firmwareTargetNote }}</span>
            </div>
            <div class="maintenance-actions">
              <button
                class="btn btn-ghost btn-sm"
                type="button"
                :disabled="!canRunHostAction('bootstrap')"
                :title="actionDisabledTitle('bootstrap')"
                @click="confirmAdvanced('bootstrap')"
              >
                <i class="fas fa-tools" aria-hidden="true"></i> Bootstrap
              </button>
              <button
                class="btn btn-primary btn-sm"
                type="button"
                :disabled="!canRunHostAction('firmware')"
                :title="actionDisabledTitle('firmware')"
                @click="runFirmwareScan"
              >
                <i class="fas fa-list" aria-hidden="true"></i> Firmware Inventory
              </button>
              <button
                class="btn btn-danger btn-sm"
                type="button"
                :disabled="!canRunHostAction('firmware')"
                :title="actionDisabledTitle('firmware')"
                @click="confirmAdvanced('firmware')"
              >
                <i class="fas fa-microchip" aria-hidden="true"></i> Firmware Update
              </button>
            </div>
            <div class="job-stack">
              <JobInlineStatus
                v-for="(id, idx) in bootstrapJobIds"
                :key="id"
                :job-id="id"
                label="Host bootstrap"
                @dismiss="bootstrapJobIds.splice(idx, 1)"
              />
              <JobInlineStatus
                v-for="(id, idx) in firmwareJobIds"
                :key="id"
                :job-id="id"
                label="Firmware"
                @dismiss="firmwareJobIds.splice(idx, 1)"
              />
            </div>
          </div>
        </div>
      </div>
      <div class="col-4 col-md-6 col-sm-12">
        <div class="card maintenance-card">
          <div class="card-body">
            <div class="maintenance-card-header">
              <h4><i class="fas fa-pause-circle section-icon" aria-hidden="true"></i> Drain / Resume</h4>
              <span class="maintenance-impact impact-danger">Workloads</span>
            </div>
            <p class="maintenance-card-copy">
              Inspect active GPU work and cordon, drain, or resume Kubernetes nodes when kubectl is configured.
            </p>
            <div class="target-chip">
              <i class="fas fa-crosshairs" aria-hidden="true"></i>
              <span>{{ actionTargetLabel('drain') }}</span>
            </div>
            <div class="maintenance-actions">
              <button
                class="btn btn-primary btn-sm"
                type="button"
                :disabled="!canRunHostAction('drain')"
                :title="actionDisabledTitle('drain')"
                @click="runDrainStatus"
              >
                <i class="fas fa-search" aria-hidden="true"></i> Status
              </button>
              <button
                class="btn btn-danger btn-sm"
                type="button"
                :disabled="!canRunHostAction('drain')"
                :title="actionDisabledTitle('drain')"
                @click="confirmAdvanced('drain')"
              >
                <i class="fas fa-pause" aria-hidden="true"></i> Drain
              </button>
              <button
                class="btn btn-green btn-sm"
                type="button"
                :disabled="!canRunHostAction('drain')"
                :title="actionDisabledTitle('drain')"
                @click="confirmAdvanced('resume')"
              >
                <i class="fas fa-play" aria-hidden="true"></i> Resume
              </button>
            </div>
            <div class="job-stack">
              <JobInlineStatus
                v-for="(id, idx) in drainJobIds"
                :key="id"
                :job-id="id"
                label="Drain / resume"
                @dismiss="drainJobIds.splice(idx, 1)"
              />
            </div>
          </div>
        </div>
      </div>
      <div class="col-4 col-md-6 col-sm-12">
        <div class="card maintenance-card">
          <div class="card-body">
            <div class="maintenance-card-header">
              <h4><i class="fas fa-th-large section-icon" aria-hidden="true"></i> MIG</h4>
              <span class="maintenance-impact impact-danger">GPU mode</span>
            </div>
            <p class="maintenance-card-copy">
              Query or toggle MIG mode on DGX Workstation hosts after confirming GPUs are idle.
            </p>
            <div class="target-chip">
              <i class="fas fa-crosshairs" aria-hidden="true"></i>
              <span>{{ actionTargetLabel('mig') }}</span>
            </div>
            <div class="maintenance-actions">
              <button
                class="btn btn-primary btn-sm"
                type="button"
                :disabled="!canRunHostAction('mig')"
                :title="actionDisabledTitle('mig')"
                @click="runMigStatus"
              >
                <i class="fas fa-search" aria-hidden="true"></i> Status
              </button>
              <button
                class="btn btn-danger btn-sm"
                type="button"
                :disabled="!canRunHostAction('mig')"
                :title="actionDisabledTitle('mig')"
                @click="confirmAdvanced('mig-enable')"
              >
                <i class="fas fa-toggle-on" aria-hidden="true"></i> Enable
              </button>
              <button
                class="btn btn-danger btn-sm"
                type="button"
                :disabled="!canRunHostAction('mig')"
                :title="actionDisabledTitle('mig')"
                @click="confirmAdvanced('mig-disable')"
              >
                <i class="fas fa-toggle-off" aria-hidden="true"></i> Disable
              </button>
            </div>
            <div class="job-stack">
              <JobInlineStatus
                v-for="(id, idx) in migJobIds"
                :key="id"
                :job-id="id"
                label="MIG"
                @dismiss="migJobIds.splice(idx, 1)"
              />
            </div>
          </div>
        </div>
      </div>
    </section>

    <ConfirmDialog
      :visible="dockerConfirm.visible"
      :title="`Clean Docker on ${dockerConfirm.label}`"
      :message="`This prunes unused Docker images, build cache, networks, and containerd images on ${dockerConfirm.label}. Running containers and volumes are not removed. Estimated duration: about ${Math.max(2, dockerConfirm.count)} minutes.`"
      confirm-text="Start cleanup"
      :danger-mode="true"
      :require-text="dockerConfirm.requireText"
      @confirm="runDockerCleanupConfirmed"
      @cancel="dockerConfirm.visible = false"
    />

    <ConfirmDialog
      :visible="advancedConfirm.visible"
      :title="advancedConfirm.title"
      :message="advancedConfirm.message"
      :confirm-text="advancedConfirm.confirmText"
      :danger-mode="advancedConfirm.dangerMode"
      :require-text="advancedConfirm.requireText"
      @confirm="runAdvancedConfirmed"
      @cancel="advancedConfirm.visible = false"
    />

    <!-- Documentation Index -->
    <section id="docs" ref="docsRef" class="card section-card">
      <div class="card-body">
        <div class="flex items-center justify-between" style="margin-bottom: var(--space-sm); flex-wrap: wrap; gap: var(--space-xs)">
          <h4><i class="fas fa-book section-icon" aria-hidden="true"></i> DGX Help Documentation Index</h4>
          <button
            class="btn btn-primary btn-sm"
            type="button"
            :disabled="docsIndex.running"
            @click="confirmReindex = true"
          >
            <i :class="['fas', docsIndex.running ? 'fa-spinner fa-spin' : 'fa-redo']" aria-hidden="true"></i>
            {{ docsIndex.running ? "Reindexing…" : "Reindex Documentation" }}
          </button>
        </div>
        <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: var(--space-sm)">
          The DGX Help chatbot answers questions using NVIDIA documentation embedded in Milvus.
          Reindex after editing <code class="docs-path">docs/urls.txt</code>, local <code class="docs-path">docs/*.md</code> guidance, or switching the embedding model.
        </p>

        <div class="docs-stats">
          <div class="docs-stat">
            <div class="docs-stat-label">Indexed chunks</div>
            <div class="docs-stat-value">
              <template v-if="docsIndex.last_count !== null">{{ docsIndex.last_count }}</template>
              <span v-else class="docs-stat-muted">unknown</span>
            </div>
          </div>
          <div class="docs-stat">
            <div class="docs-stat-label">Last reindex</div>
            <div class="docs-stat-value">
              <template v-if="docsIndex.last_indexed_at">{{ formatTime(docsIndex.last_indexed_at) }}</template>
              <span v-else class="docs-stat-muted">never (using container startup ingest)</span>
            </div>
          </div>
          <div class="docs-stat">
            <div class="docs-stat-label">Status</div>
            <div class="docs-stat-value">
              <span :class="['badge', docsPhaseBadge]">{{ docsPhaseLabel }}</span>
            </div>
          </div>
        </div>

        <div v-if="docsIndex.running || docsIndex.phase === 'success' || docsIndex.phase === 'error'" class="docs-progress">
          <div v-if="docsIndex.running" class="docs-progress-bar-wrap">
            <div class="progress-bar">
              <div
                class="progress-fill good"
                :style="{
                  width: docsIndex.total
                    ? Math.round((docsIndex.progress / docsIndex.total) * 100) + '%'
                    : '8%'
                }"
              ></div>
            </div>
            <div class="docs-progress-text">
              <span><i class="fas fa-spinner fa-spin" aria-hidden="true"></i> {{ docsIndex.message || docsIndex.phase }}</span>
              <span v-if="docsIndex.total">{{ docsIndex.progress }} / {{ docsIndex.total }}</span>
            </div>
          </div>
          <div v-else-if="docsIndex.phase === 'error'" class="docs-error">
            <i class="fas fa-exclamation-triangle" aria-hidden="true"></i>
            <span>{{ docsIndex.error || "Reindex failed" }}</span>
          </div>
          <div v-else-if="docsIndex.phase === 'success'" class="docs-success">
            <i class="fas fa-check-circle" aria-hidden="true"></i>
            <span>{{ docsIndex.message }}</span>
          </div>
        </div>
      </div>
    </section>

    <ConfirmDialog
      :visible="confirmReindex"
      title="Reindex documentation"
      message="This crawls every site prefix in docs/urls.txt, includes local docs/*.md guidance, converts content to Markdown, drops the current Milvus collection, and re-embeds the documentation. DGX Help may return empty results until reindexing completes. Existing chats are unaffected."
      confirm-text="Start reindex"
      :danger-mode="true"
      @confirm="startReindex"
      @cancel="confirmReindex = false"
    />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, reactive, nextTick } from "vue";
import { useIntervalFn, useDocumentVisibility } from "@vueuse/core";
import {
  getDiskUsage, getHosts, getRebootRequired, rebootHosts, runSystemMaintenance, runDockerCleanup,
  runStorageAnalysis, getStorageAnalysis, runGpuUsage, getGpuUsage,
  runPreflightCheck, runHealthDiagnostics, runHostBootstrap, runFirmwareInventory, runFirmwareUpdate,
  runDrainAction, runMigAction,
  getDocsIndexStatus, reindexDocs,
} from "../api.js";
import { getMachineType } from "../machineTypes.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import JobInlineStatus from "../components/JobInlineStatus.vue";
import InfoTooltip from "../components/InfoTooltip.vue";
import PageIntro from "../components/PageIntro.vue";
import { GLOSSARY } from "../glossary.js";
import { sortHostnames } from "../utils/hosts.js";

const sections = [
  { id: "targets", label: "Targets", icon: "fa-crosshairs" },
  { id: "disk", label: "Disk", icon: "fa-hdd" },
  { id: "reboot", label: "Reboot", icon: "fa-power-off" },
  { id: "storage", label: "Storage", icon: "fa-chart-pie" },
  { id: "gpu", label: "GPU", icon: "fa-microchip" },
  { id: "actions", label: "Quick", icon: "fa-bolt" },
  { id: "advanced", label: "Advanced", icon: "fa-screwdriver-wrench" },
  { id: "docs", label: "Docs", icon: "fa-book" },
];

function askHelpChat(prompt) {
  window.dispatchEvent(new CustomEvent("helpchat:open", { detail: { prompt } }));
}

const diskUsage = ref([]);
const hosts = ref([]);
const allHosts = ref([]);
const targetMode = ref("all");
const selectedTargets = ref([]);
const rebootHosts_ = ref([]);
const rebootAllOpen = ref(false);
const confirmSingleReboot = reactive({ visible: false, hostname: "" });
const targetedRebootConfirm = reactive({ visible: false, hosts: [], label: "", count: 0, requireText: "" });
const dockerConfirm = reactive({ visible: false, hosts: null, label: "", count: 0, requireText: "" });
const advancedConfirm = reactive({
  visible: false,
  action: "",
  title: "",
  message: "",
  confirmText: "Start",
  requireText: "",
  dangerMode: true,
  hosts: null,
});

const storageData = ref([]);
const analysisRunning = ref(false);
const storageJobId = ref("");
const gpuData = ref([]);
const gpuRunning = ref(false);
const gpuJobId = ref("");
const rebootJobIds = ref([]);
const systemMaintenanceJobIds = ref([]);
const dockerJobIds = ref([]);
const preflightJobIds = ref([]);
const healthJobIds = ref([]);
const bootstrapJobIds = ref([]);
const firmwareJobIds = ref([]);
const drainJobIds = ref([]);
const migJobIds = ref([]);
const expandedMounts = ref(new Set());

// Storage and GPU cards stretch to full width once they have content; this
// way the 2x2 layout reads tidily when empty but the data tables aren't
// cramped once there's something to look at.
const storageWide = computed(() => storageData.value.length > 0 || analysisRunning.value || !!storageJobId.value);
const gpuWide = computed(() => gpuData.value.length > 0 || gpuRunning.value || !!gpuJobId.value);

const activeSection = ref("targets");
const targetsRef = ref(null);
const diskRef = ref(null);
const rebootRef = ref(null);
const storageRef = ref(null);
const gpuRef = ref(null);
const actionsRef = ref(null);
const advancedRef = ref(null);
const docsRef = ref(null);

const confirmReindex = ref(false);
const docsIndex = ref({
  running: false,
  phase: "idle",
  message: "",
  progress: 0,
  total: 0,
  last_count: null,
  last_indexed_at: null,
  error: null,
});
let docsPoll = null;

const visibility = useDocumentVisibility();

const docsPhaseBadge = computed(() => {
  const map = {
    idle: "badge-outline",
    loading: "badge-blue",
    embedding: "badge-blue",
    inserting: "badge-blue",
    success: "badge-green",
    error: "badge-red",
  };
  return map[docsIndex.value.phase] || "badge-outline";
});
const docsPhaseLabel = computed(() => {
  const map = {
    idle: "Idle",
    loading: "Loading docs",
    embedding: "Embedding",
    inserting: "Writing",
    success: "Up to date",
    error: "Error",
  };
  return map[docsIndex.value.phase] || docsIndex.value.phase;
});

const rebootAllConfirmWord = computed(() => `REBOOT ${rebootHosts_.value.length}`);

const ACTION_TARGETS = {
  firmware: {
    allLabel: "all hosts (capability detected at runtime)",
    supports: () => true,
  },
  gpu: {
    allLabel: "all GPU hosts",
    supports: (h) => getMachineType(h.machine_type).hasGpu,
  },
  mig: {
    allLabel: "all DGX Workstation hosts",
    supports: (h) => h.machine_type === "dgx_workstation",
  },
};

function actionTargetConfig(action) {
  return ACTION_TARGETS[action] || {
    allLabel: "all hosts",
    supports: () => true,
  };
}

function supportedHostsForAction(action) {
  const config = actionTargetConfig(action);
  return allHosts.value.filter((h) => config.supports(h));
}

function unsupportedSelectedHosts(action) {
  if (targetMode.value !== "selected") return [];
  const config = actionTargetConfig(action);
  const byName = new Map(allHosts.value.map((h) => [h.hostname, h]));
  return sortHostnames(selectedTargets.value).filter((hostname) => {
    const host = byName.get(hostname);
    return !host || !config.supports(host);
  });
}

const targetSummary = computed(() => {
  if (targetMode.value === "all") return `All hosts (${allHosts.value.length})`;
  const count = selectedTargets.value.length;
  if (count === 0) return "No hosts selected";
  if (count === 1) return selectedTargets.value[0];
  return `${count} selected hosts`;
});

const firmwareTargetNote = computed(() => {
  const unsupported = unsupportedSelectedHosts("firmware");
  if (!unsupported.length) return "";
  return `${unsupported.length} unsupported target${unsupported.length === 1 ? "" : "s"}`;
});

function setTargetMode(mode) {
  targetMode.value = mode;
}

function selectAllTargets() {
  selectedTargets.value = allHosts.value.map((h) => h.hostname);
}

function selectGpuTargets() {
  selectedTargets.value = allHosts.value
    .filter((h) => getMachineType(h.machine_type).hasGpu)
    .map((h) => h.hostname);
}

function selectWorkstationTargets() {
  selectedTargets.value = allHosts.value
    .filter((h) => h.machine_type === "dgx_workstation")
    .map((h) => h.hostname);
}

function clearTargetSelection() {
  selectedTargets.value = [];
}

function canRunHostAction(action) {
  if (!allHosts.value.length) return false;
  if (targetMode.value === "all") return supportedHostsForAction(action).length > 0;
  return selectedTargets.value.length > 0 && unsupportedSelectedHosts(action).length === 0;
}

function actionDisabledTitle(action) {
  if (!allHosts.value.length) return "No hosts are available";
  if (targetMode.value === "selected" && !selectedTargets.value.length) {
    return "Select at least one host";
  }
  const unsupported = unsupportedSelectedHosts(action);
  if (unsupported.length) {
    return `Unsupported target${unsupported.length === 1 ? "" : "s"} for this action: ${unsupported.join(", ")}`;
  }
  return "";
}

function actionTargetLabel(action) {
  if (targetMode.value === "all") return actionTargetConfig(action).allLabel;
  const count = selectedTargets.value.length;
  if (count === 0) return "no selected hosts";
  if (count === 1) return selectedTargets.value[0];
  return `${count} selected hosts`;
}

function targetSnapshot(action, options = {}) {
  const explicitAll = !!options.explicitAll;
  const isAll = targetMode.value === "all";
  const supported = supportedHostsForAction(action);
  const hosts = isAll
    ? (explicitAll ? supported.map((h) => h.hostname) : null)
    : sortHostnames(selectedTargets.value);
  return {
    hosts,
    label: actionTargetLabel(action),
    count: isAll ? supported.length : selectedTargets.value.length,
    isAll,
  };
}

function payloadFromSnapshot(snapshot) {
  return snapshot.hosts ? { hosts: snapshot.hosts } : { all_hosts: true };
}

function payloadForAction(action, options = {}) {
  return payloadFromSnapshot(targetSnapshot(action, options));
}

function mountKey(hostname, mountpoint) {
  return `${hostname}::${mountpoint}`;
}

function toggleMount(hostname, mountpoint) {
  const key = mountKey(hostname, mountpoint);
  if (expandedMounts.value.has(key)) expandedMounts.value.delete(key);
  else expandedMounts.value.add(key);
  expandedMounts.value = new Set(expandedMounts.value);
}

function isMountExpanded(hostname, mountpoint) {
  return expandedMounts.value.has(mountKey(hostname, mountpoint));
}

async function load() {
  try {
    diskUsage.value = await getDiskUsage();
    const hostData = await getHosts();
    allHosts.value = hostData;
    hosts.value = hostData.map((h) => h.hostname);
    const knownHosts = new Set(hosts.value);
    selectedTargets.value = selectedTargets.value.filter((h) => knownHosts.has(h));
    rebootHosts_.value = await getRebootRequired();
    try { storageData.value = await getStorageAnalysis(); } catch { /* no cached data */ }
    try { gpuData.value = await getGpuUsage(); } catch { /* no cached data */ }
    try { docsIndex.value = await getDocsIndexStatus(); } catch { /* docs index optional */ }
  } catch (e) {
    window.$toast?.error("Couldn't load maintenance data", e);
  }
}

async function startReindex() {
  confirmReindex.value = false;
  try {
    await reindexDocs();
    window.$toast?.success("Documentation reindex started");
    startDocsPoll();
  } catch (e) {
    if (e?.status === 409) {
      window.$toast?.info("A reindex is already running");
      startDocsPoll();
    } else {
      window.$toast?.error("Couldn't start reindex", e);
    }
  }
}

function startDocsPoll() {
  stopDocsPoll();
  docsPoll = useIntervalFn(async () => {
    if (visibility.value !== "visible") return;
    try {
      const status = await getDocsIndexStatus();
      docsIndex.value = status;
      if (!status.running) {
        stopDocsPoll();
        if (status.phase === "success") {
          window.$toast?.success(status.message || "Documentation reindex complete");
        } else if (status.phase === "error") {
          window.$toast?.error("Documentation reindex failed", { details: status.error || "" });
        }
      }
    } catch (e) {
      stopDocsPoll();
      window.$toast?.error("Lost connection while polling reindex status", e);
    }
  }, 1500, { immediate: true });
}

function stopDocsPoll() {
  docsPoll?.pause();
  docsPoll = null;
}

function formatTime(dt) {
  if (!dt) return "--";
  const str = String(dt).endsWith("Z") || String(dt).includes("+") ? dt : dt + "Z";
  return new Date(str).toLocaleString("en-US", { timeZone: "America/Los_Angeles" });
}

async function runAnalysis() {
  if (!canRunHostAction("storage")) {
    window.$toast?.error(actionDisabledTitle("storage") || "Storage analysis target is invalid");
    return;
  }
  analysisRunning.value = true;
  try {
    const result = await runStorageAnalysis(payloadForAction("storage"));
    if (result?.job_id) {
      storageJobId.value = result.job_id;
    } else {
      // No job_id back — backend ran synchronously. Refresh data.
      analysisRunning.value = false;
      try { storageData.value = await getStorageAnalysis(); } catch { /* ignore */ }
    }
  } catch (e) {
    analysisRunning.value = false;
    window.$toast?.error("Couldn't start storage analysis", e);
  }
}

async function onStorageDone() {
  analysisRunning.value = false;
  try {
    storageData.value = await getStorageAnalysis();
    window.$toast?.success("Storage analysis complete");
  } catch (e) {
    window.$toast?.error("Couldn't load storage analysis results", e);
  }
}
function onStorageFailed(job) {
  analysisRunning.value = false;
  window.$toast?.error("Storage analysis failed", { details: job?.error_summary || "See Job History" });
}

async function runGpuAnalysis() {
  if (!canRunHostAction("gpu")) {
    window.$toast?.error(actionDisabledTitle("gpu") || "GPU usage target is invalid");
    return;
  }
  gpuRunning.value = true;
  try {
    const result = await runGpuUsage(payloadForAction("gpu"));
    if (result?.job_id) {
      gpuJobId.value = result.job_id;
    } else {
      gpuRunning.value = false;
      try { gpuData.value = await getGpuUsage(); } catch { /* ignore */ }
    }
  } catch (e) {
    gpuRunning.value = false;
    window.$toast?.error("Couldn't start GPU usage analysis", e);
  }
}

async function onGpuDone() {
  gpuRunning.value = false;
  try {
    gpuData.value = await getGpuUsage();
    window.$toast?.success("GPU usage analysis complete");
  } catch (e) {
    window.$toast?.error("Couldn't load GPU usage results", e);
  }
}
function onGpuFailed(job) {
  gpuRunning.value = false;
  window.$toast?.error("GPU usage analysis failed", { details: job?.error_summary || "See Job History" });
}

function openRebootAll() { rebootAllOpen.value = true; }

function trackJob(list, id) {
  if (id && !list.value.includes(id)) list.value.push(id);
}

async function rebootAll() {
  rebootAllOpen.value = false;
  try {
    const result = await rebootHosts({ all_hosts: true });
    if (result?.job_id) trackJob(rebootJobIds, result.job_id);
    window.$toast?.success(result?.detail || `Rebooting ${rebootHosts_.value.length} host(s)`);
  } catch (e) {
    window.$toast?.error("Couldn't start fleet reboot", e);
  }
}

function onRebootDone() { /* JobInlineStatus shows success state; user dismisses when done */ }
function onRebootFailed(id) {
  window.$toast?.error("Reboot failed", { details: `Job ${id} — see Job History` });
}

function askRebootSingle(hostname) {
  if (!hostname) return;
  confirmSingleReboot.hostname = hostname;
  confirmSingleReboot.visible = true;
}

async function doSingleReboot() {
  const target = confirmSingleReboot.hostname;
  confirmSingleReboot.visible = false;
  if (!target) return;
  try {
    const result = await rebootHosts({ hosts: [target] });
    if (result?.job_id) trackJob(rebootJobIds, result.job_id);
    window.$toast?.success(result?.detail || `Rebooting ${target}`);
  } catch (e) {
    window.$toast?.error(`Couldn't reboot ${target}`, e);
  }
}

function askTargetedReboot() {
  if (!canRunHostAction("reboot")) {
    window.$toast?.error(actionDisabledTitle("reboot") || "Reboot target is invalid");
    return;
  }
  const snapshot = targetSnapshot("reboot", { explicitAll: true });
  Object.assign(targetedRebootConfirm, {
    visible: true,
    hosts: snapshot.hosts || [],
    label: snapshot.label,
    count: snapshot.count,
    requireText: snapshot.count > 1 ? `REBOOT ${snapshot.count}` : "",
  });
}

async function doTargetedReboot() {
  const hostsToReboot = sortHostnames(targetedRebootConfirm.hosts);
  targetedRebootConfirm.visible = false;
  if (!hostsToReboot.length) return;
  try {
    const result = await rebootHosts({ hosts: hostsToReboot });
    if (result?.job_id) trackJob(rebootJobIds, result.job_id);
    window.$toast?.success(result?.detail || `Rebooting ${hostsToReboot.length} host(s)`);
  } catch (e) {
    window.$toast?.error("Couldn't start targeted reboot", e);
  }
}

function askDockerCleanup() {
  if (!canRunHostAction("docker")) {
    window.$toast?.error(actionDisabledTitle("docker") || "Docker cleanup target is invalid");
    return;
  }
  const snapshot = targetSnapshot("docker");
  Object.assign(dockerConfirm, {
    visible: true,
    hosts: snapshot.hosts,
    label: snapshot.label,
    count: snapshot.count,
    requireText: snapshot.count > 1 ? `CLEAN ${snapshot.count}` : "",
  });
}

async function runDockerCleanupConfirmed() {
  const payload = payloadFromSnapshot(dockerConfirm);
  const label = dockerConfirm.label;
  dockerConfirm.visible = false;
  try {
    const result = await runDockerCleanup(payload);
    if (result?.job_id) trackJob(dockerJobIds, result.job_id);
    window.$toast?.success(`Docker cleanup started on ${label}`);
  } catch (e) {
    window.$toast?.error("Couldn't start Docker cleanup", e);
  }
}

async function startAction(apiCall, jobList, successMessage, payload = {}) {
  try {
    const result = await apiCall(payload);
    if (result?.job_id) trackJob(jobList, result.job_id);
    window.$toast?.success(result?.detail || successMessage);
  } catch (e) {
    window.$toast?.error(successMessage.replace("started", "failed"), e);
  }
}

async function runPreflight() {
  if (!canRunHostAction("preflight")) {
    window.$toast?.error(actionDisabledTitle("preflight") || "Preflight target is invalid");
    return;
  }
  await startAction(runPreflightCheck, preflightJobIds, "Preflight check started", payloadForAction("preflight"));
}

async function runHealth() {
  if (!canRunHostAction("health")) {
    window.$toast?.error(actionDisabledTitle("health") || "Diagnostics target is invalid");
    return;
  }
  await startAction(runHealthDiagnostics, healthJobIds, "Health diagnostics started", payloadForAction("health"));
}

async function runFirmwareScan() {
  if (!canRunHostAction("firmware")) {
    window.$toast?.error(actionDisabledTitle("firmware") || "Firmware inventory target is invalid");
    return;
  }
  await startAction(runFirmwareInventory, firmwareJobIds, "Firmware inventory started", payloadForAction("firmware"));
}

async function runDrainStatus() {
  if (!canRunHostAction("drain")) {
    window.$toast?.error(actionDisabledTitle("drain") || "Drain target is invalid");
    return;
  }
  await startAction((data) => runDrainAction("status", data), drainJobIds, "Drain status started", payloadForAction("drain"));
}

async function runMigStatus() {
  if (!canRunHostAction("mig")) {
    window.$toast?.error(actionDisabledTitle("mig") || "MIG target is invalid");
    return;
  }
  await startAction((data) => runMigAction("status", data), migJobIds, "MIG status started", payloadForAction("mig"));
}

function confirmAdvanced(action) {
  const actionTargets = {
    system: "system",
    bootstrap: "bootstrap",
    firmware: "firmware",
    drain: "drain",
    resume: "drain",
    "mig-enable": "mig",
    "mig-disable": "mig",
  };
  const targetAction = actionTargets[action];
  if (!canRunHostAction(targetAction)) {
    window.$toast?.error(actionDisabledTitle(targetAction) || "Maintenance target is invalid");
    return;
  }
  const snapshot = targetSnapshot(targetAction);
  const target = snapshot.label;
  const configs = {
    system: {
      title: `Run full system maintenance on ${target}`,
      message: `This runs package and firmware updates, mount configuration and remediation, kernel and container cleanup, storage checks, and zombie-process remediation on ${target}. It automatically reboots a host after firmware changes or when zombie processes are detected. Estimated duration: about ${Math.max(15, snapshot.count * 15)} minutes.`,
      confirmText: "Run maintenance",
      requireText: snapshot.count > 1 ? "MAINTENANCE" : "",
      dangerMode: true,
    },
    bootstrap: {
      title: `Bootstrap ${target}`,
      message: `This installs common groups, admin sudo configuration, Docker, NVIDIA Container Toolkit, and then scans ${target}.`,
      confirmText: "Start bootstrap",
      requireText: snapshot.count > 1 ? "BOOTSTRAP" : "",
      dangerMode: true,
    },
    firmware: {
      title: `Update firmware on ${target}`,
      message: `This refreshes firmware metadata and applies available firmware updates on ${target}. A reboot may be required afterward.`,
      confirmText: "Start firmware update",
      requireText: snapshot.count > 1 ? "FIRMWARE" : "",
      dangerMode: true,
    },
    drain: {
      title: `Drain ${target}`,
      message: `This checks active GPU work, cordons Kubernetes nodes when available, and attempts kubectl drain on ${target}.`,
      confirmText: "Drain",
      requireText: snapshot.count > 1 ? "DRAIN" : "",
      dangerMode: true,
    },
    resume: {
      title: `Resume ${target}`,
      message: `This runs kubectl uncordon where Kubernetes access is available on ${target}.`,
      confirmText: "Resume",
      requireText: "",
      dangerMode: false,
    },
    "mig-enable": {
      title: `Enable MIG on ${target}`,
      message: `This toggles MIG mode on DGX Workstation hosts after refusing to run if active GPU processes are detected.`,
      confirmText: "Enable MIG",
      requireText: snapshot.count > 1 ? "MIG" : "",
      dangerMode: true,
    },
    "mig-disable": {
      title: `Disable MIG on ${target}`,
      message: `This disables MIG mode on DGX Workstation hosts after refusing to run if active GPU processes are detected.`,
      confirmText: "Disable MIG",
      requireText: snapshot.count > 1 ? "MIG" : "",
      dangerMode: true,
    },
  };
  Object.assign(advancedConfirm, {
    visible: true,
    action,
    hosts: snapshot.hosts,
    ...configs[action],
  });
}

async function runAdvancedConfirmed() {
  const action = advancedConfirm.action;
  const payload = payloadFromSnapshot(advancedConfirm);
  advancedConfirm.visible = false;
  if (action === "system") {
    await startAction(runSystemMaintenance, systemMaintenanceJobIds, "Full system maintenance started", payload);
  } else if (action === "bootstrap") {
    await startAction(runHostBootstrap, bootstrapJobIds, "Host bootstrap started", payload);
  } else if (action === "firmware") {
    await startAction(runFirmwareUpdate, firmwareJobIds, "Firmware update started", payload);
  } else if (action === "drain") {
    await startAction((data) => runDrainAction("drain", data), drainJobIds, "Drain started", payload);
  } else if (action === "resume") {
    await startAction((data) => runDrainAction("resume", data), drainJobIds, "Resume started", payload);
  } else if (action === "mig-enable") {
    await startAction((data) => runMigAction("enable", data), migJobIds, "MIG enable started", payload);
  } else if (action === "mig-disable") {
    await startAction((data) => runMigAction("disable", data), migJobIds, "MIG disable started", payload);
  }
}

function diskClass(pct) {
  if (!pct) return "good";
  if (pct >= 90) return "danger";
  if (pct >= 75) return "warn";
  return "good";
}

function mountBadgeClass(type) {
  if (type === "raid") return "badge-orange";
  if (["nfs", "smb", "network", "iscsi"].includes(type)) return "badge-blue";
  return "badge-outline";
}

function formatSize(mb) {
  const val = parseInt(mb) || 0;
  if (val >= 1024 * 1024) return (val / (1024 * 1024)).toFixed(1) + " TB";
  if (val >= 1024) return (val / 1024).toFixed(1) + " GB";
  return val + " MB";
}

function pct(part, total) {
  const t = parseInt(total) || 1;
  const p = parseInt(part) || 0;
  return Math.min(100, Math.round((p / t) * 100));
}

function barColor(part, total) {
  const p = pct(part, total);
  if (p >= 50) return "danger";
  if (p >= 25) return "warn";
  return "good";
}

function gpuStatusClass(status) {
  if (status === "free") return "badge-green";
  if (status === "idle_reserved") return "badge-orange";
  return "badge-blue";
}

function gpuStatusLabel(status) {
  if (status === "free") return "Free";
  if (status === "idle_reserved") return "Idle / Reserved";
  return "Active";
}

function gpuMemPct(gpu) {
  if (!gpu.memory_total_mb) return 0;
  return Math.round((gpu.memory_used_mb / gpu.memory_total_mb) * 100);
}

function gpuMemoryLabel(gpu, report) {
  if (gpu.memory_supported === false || report?.memory_architecture === "UMA") {
    const processMemory = gpu.memory_used_mb ? `${formatSize(gpu.memory_used_mb)} process` : "framebuffer N/A";
    const available = report?.system_memory?.mem_available_mb
      ? ` · ${formatSize(report.system_memory.mem_available_mb)} system available`
      : "";
    return processMemory + available;
  }
  return `${formatSize(gpu.memory_used_mb)} / ${formatSize(gpu.memory_total_mb)}`;
}

async function goToSection(id) {
  activeSection.value = id;
  await nextTick();
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

let scrollObserver = null;
function setupSectionObserver() {
  if (!("IntersectionObserver" in window)) return;
  scrollObserver = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) activeSection.value = e.target.id;
      }
    },
    { rootMargin: "-30% 0px -60% 0px", threshold: 0 }
  );
  for (const el of [targetsRef.value, diskRef.value, rebootRef.value, storageRef.value, gpuRef.value, actionsRef.value, advancedRef.value, docsRef.value]) {
    if (el) scrollObserver.observe(el);
  }
}

onMounted(async () => {
  await load();
  await nextTick();
  setupSectionObserver();
  // If a reindex is already running when we arrive, start polling immediately.
  if (docsIndex.value?.running) startDocsPoll();
});

onUnmounted(() => {
  stopDocsPoll();
  scrollObserver?.disconnect();
});
</script>

<style scoped>
.section-nav {
  position: sticky;
  top: 64px;
  z-index: 5;
  display: flex;
  gap: 4px;
  background: var(--surface-white);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 6px;
  margin-bottom: var(--space-md);
  box-shadow: var(--shadow-card);
  overflow-x: auto;
}

.section-nav-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  text-decoration: none;
  white-space: nowrap;
  transition: var(--transition-standard);
}

.section-nav-link:hover {
  color: var(--text-on-light);
  background: var(--surface-lighter);
}

.section-nav-link.active {
  color: var(--text-on-dark);
  background: var(--surface-dark);
}

.section-icon {
  color: var(--text-secondary);
  margin-right: 6px;
  font-size: 0.9em;
}

.section-intro {
  margin: 0 0 var(--space-sm);
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.45;
  max-width: 720px;
}

.section-heading {
  margin: 0 0 var(--space-xs);
}

.target-card .card-body {
  padding-bottom: 12px;
}

.target-card-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(180px, 260px);
  gap: var(--space-sm);
  align-items: start;
}

.target-intro {
  margin-bottom: 0;
}

.target-summary-panel {
  display: flex;
  flex-direction: column;
  gap: 3px;
  align-items: flex-start;
  justify-content: center;
  min-height: 58px;
  padding: 10px 12px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  background: var(--surface-light);
}

.target-summary-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0;
}

.target-summary-value {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-on-light);
  line-height: 1.25;
}

.target-control-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-xs);
  margin-top: var(--space-sm);
}

.target-mode,
.target-select-tools {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
}

.target-select-panel {
  border-top: 1px solid var(--border-subtle);
  margin-top: var(--space-sm);
  padding-top: var(--space-sm);
}

.target-checkboxes {
  max-height: 180px;
  overflow-y: auto;
  padding: var(--space-xs);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  background: var(--surface-light);
}

.target-checkbox {
  background: var(--surface-white);
  min-height: 34px;
}

.target-host-name {
  font-family: var(--font-mono);
  font-size: 12px;
}

.target-checkbox .badge {
  font-size: 10px;
  padding: 2px 6px;
}

.target-warning,
.target-line {
  margin: 0 0 var(--space-xs);
  font-size: 12px;
  color: var(--text-secondary);
}

.target-line {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 4px 8px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  background: var(--surface-light);
}

.target-warning {
  margin-top: var(--space-xs);
  color: var(--color-danger);
}

.maintenance-group-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: calc(var(--space-xs) * -0.5);
  padding: 2px 0;
}

.maintenance-group-heading h4 {
  margin: 0;
  font-size: 15px;
}

.maintenance-group-heading p {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.maintenance-group-heading.advanced {
  margin-top: var(--space-sm);
  padding-top: var(--space-sm);
  border-top: 1px solid var(--border-subtle);
}

.maintenance-card {
  height: 100%;
}

.maintenance-card .card-body {
  min-height: 214px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.maintenance-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-xs);
  margin-bottom: var(--space-xs);
}

.maintenance-card-header h4 {
  margin: 0;
  font-size: 16px;
  line-height: 1.25;
}

.maintenance-impact {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 3px 7px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
  font-size: 10px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0;
}

.impact-read {
  color: var(--color-info);
  background: var(--surface-info-soft);
  border-color: rgba(0, 116, 223, 0.28);
}

.impact-change {
  color: var(--text-secondary);
  background: var(--surface-light);
}

.impact-danger {
  color: var(--color-danger);
  background: var(--surface-danger-soft);
  border-color: rgba(229, 32, 32, 0.25);
}

.maintenance-card-copy {
  min-height: 42px;
  margin: 0 0 var(--space-xs);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.4;
}

.target-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  align-self: flex-start;
  max-width: 100%;
  margin-bottom: var(--space-sm);
  padding: 5px 8px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  background: var(--surface-light);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.25;
}

.target-chip span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.maintenance-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
  margin-top: auto;
}

.maintenance-actions .btn {
  min-height: 32px;
}

.job-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  margin-top: var(--space-xs);
}

.ask-helper {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--space-xs);
  padding: 4px 10px;
  background: transparent;
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-info);
  cursor: pointer;
  font-family: var(--font-family);
  transition: var(--transition-standard);
}
.ask-helper:hover {
  background: var(--surface-info-soft);
  border-color: var(--color-info);
}
.ask-helper:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.gpu-note {
  margin-bottom: var(--space-sm);
  padding: var(--space-xs) var(--space-sm);
}

.gpu-note-text {
  margin-top: 2px;
  color: var(--text-secondary);
  font-size: 12px;
}

.section-card {
  margin-bottom: var(--space-md);
  scroll-margin-top: 120px;
}

.section-card-grid {
  scroll-margin-top: 120px;
  margin-bottom: var(--space-md);
  gap: var(--space-sm);
  align-items: stretch;
}

.section-card-grid > div {
  display: flex;
}

/* Top row of the 2x2 (Storage + GPU). Cards inside align to equal height
 * and the row owns the bottom margin, not the individual cards. */
.section-row {
  margin-bottom: var(--space-md);
  align-items: stretch;
}
.section-row > .section-card {
  margin-bottom: 0;
  display: flex;
  flex-direction: column;
}
.section-row > .section-card > .card-body {
  flex: 1;
}

.reboot-host-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 4px 12px;
  max-height: 200px;
  overflow-y: auto;
  background: var(--surface-light);
  padding: var(--space-xs);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
}

.reboot-host-list li {
  display: flex;
  align-items: center;
  font-size: 13px;
}

.reboot-host-list code {
  font-family: var(--font-mono);
  font-size: 12px;
}

.disk-host-row {
  display: flex;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-subtle);
  gap: var(--space-sm);
}

.disk-host-row:last-child { border-bottom: none; }

.disk-host-name { min-width: 140px; font-weight: 500; }
.disk-bars { flex: 1; display: flex; flex-direction: column; gap: 6px; }
.disk-bar-group { display: flex; align-items: center; gap: 8px; }
.disk-bar-label { font-size: 12px; color: var(--text-secondary); min-width: 36px; }
.disk-bar-pct { font-size: 12px; font-weight: 500; min-width: 36px; text-align: right; }

.storage-row {
  display: flex;
  align-items: center;
  padding: 5px 0;
  font-size: 13px;
  border-bottom: 1px solid var(--border-subtle);
}
.storage-row:last-child { border-bottom: none; }
.storage-name {
  min-width: 100px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.storage-size {
  min-width: 70px;
  text-align: right;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.sa-host { margin-bottom: var(--space-md); }
.sa-table { display: flex; flex-direction: column; gap: 2px; }
.sa-row-wrap { border-bottom: 1px solid var(--border-subtle); }
.sa-row-wrap:last-child { border-bottom: none; }
.sa-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 4px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background 0.15s;
}
.sa-row:hover { background: var(--surface-lighter); }
.sa-label {
  min-width: 180px;
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sa-bar { flex: 1; height: 8px; min-width: 80px; }
.sa-pct { min-width: 40px; text-align: right; font-size: 13px; font-weight: 600; }
.sa-pct.danger { color: var(--color-danger); }
.sa-pct.warn { color: var(--color-warning); }
.sa-sizes {
  min-width: 130px;
  text-align: right;
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.sa-expand-icon {
  font-size: 10px;
  color: var(--text-secondary);
  transition: transform 0.2s;
  min-width: 14px;
  text-align: center;
}
.sa-expand-icon.rotated { transform: rotate(180deg); }
.sa-details { padding: 4px 4px 8px 24px; }

.docs-path {
  font-family: var(--font-mono);
  background: var(--surface-lighter);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 12px;
}

.docs-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-sm);
  padding: var(--space-sm) 0;
  border-top: 1px solid var(--border-subtle);
  border-bottom: 1px solid var(--border-subtle);
  margin-bottom: var(--space-sm);
}

.docs-stat-label {
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
  margin-bottom: 4px;
}

.docs-stat-value {
  font-size: 14px;
  font-family: var(--font-mono);
  font-weight: 500;
}

.docs-stat-muted { color: var(--text-muted); font-style: italic; font-family: var(--font-family); font-weight: 400; }

.docs-progress-bar-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.docs-progress-text {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
}

.docs-progress-text i { margin-right: 6px; }

.docs-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--surface-danger-soft);
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-sm);
  color: var(--color-danger);
  font-size: 13px;
}

.docs-success {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--surface-success-soft);
  border: 1px solid var(--color-success);
  border-radius: var(--radius-sm);
  color: var(--text-on-light);
  font-size: 13px;
}
.docs-success i { color: var(--color-success); }

@media (max-width: 640px) {
  .section-nav { top: 56px; }
  .target-card-main {
    grid-template-columns: 1fr;
  }
  .target-summary-panel {
    min-height: auto;
  }
  .target-mode,
  .target-select-tools,
  .maintenance-actions {
    width: 100%;
  }
  .target-mode .btn,
  .maintenance-actions .btn {
    flex: 1 1 auto;
  }
  .maintenance-card-header {
    align-items: flex-start;
  }
  .maintenance-card .card-body {
    min-height: 0;
  }
  .target-chip {
    width: 100%;
  }
  .target-chip span {
    white-space: normal;
  }
}
</style>
