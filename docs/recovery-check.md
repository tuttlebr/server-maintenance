# Automatic health checks

At startup, Fleet repairs recovery flags left by older runners when the completed job log proves the attempt stopped before making changes. This covers rejected package previews, initial SSH failures, unavailable container runtimes before pruning, and devices never reached after those preflight failures. Activity retains the failed attempt and records why its recovery flag was cleared. No remote command runs during this repair.

A zero-change recap alone is not sufficient evidence: failed Kubernetes drains can already have changed scheduling. Interrupted jobs, timeouts, incomplete logs, and evidence of a mutation retain their recovery requirements. Package checks and explicit reboots remain available. Reboot skips preflight verification and waits for the node to return; this alone does not prove every earlier host-health issue is resolved. The next install or cleanup automatically verifies affected hosts before making changes.

The automatic check treats all devices as standalone hosts and checks mounts, systemd, Debian package configuration, and NVIDIA GPU access where applicable. It requires no Kubernetes access, maintenance-mode configuration, or node readiness check. It runs within the requested action under the same device reservation. Successful verification refreshes device facts, clears the recovery requirement, and continues the requested action. If any selected device fails, no part of the requested action starts; the job shows the specific error and can be retried after the issue is resolved. Verification does not repair services or change node scheduling.

Existing inventory metadata does not change this policy. A failed or incomplete follow-up scan keeps the affected device unverified and cannot clear its recovery requirement, even if a scan report was written before the failure. Facts scans inspect local membership files for inventory only; they do not query a cluster API.

The systemd check accepts `running` (rc=0), or `degraded` (rc=1) when every failed unit is explicitly ignored as non-critical. By default, only `motd-news.service` is ignored. The job reports ignored failures without resetting, disabling, or masking services. Other failed units, failed state queries, and unexplained degradation block recovery. The DGX Spark boot splash described below is the only accepted `starting` state.

Set `fleet_systemd_ignored_units` in inventory/group/host variables to replace the default list of exact unit names. Set it to `[]` to require zero failed units. An ignored MOTD failure cannot hide another service failure or an incomplete boot.

Mount validation ignores fstab comments, blank lines, swap, and entries with `noauto`, `nofail`, or `x-systemd.automount`. Comment detection works with the older `mawk` shipped on Jetson devices, including indented comments. Mandatory mounts and fstab validation errors still block recovery.

When this check fails, the job output includes the system state, command return codes, failed units, pending jobs, and query errors. An empty failed-unit list does not mean that boot has completed.

## DGX Spark waiting for the boot splash

Plymouth draws the boot splash on the local display. On an SSH-managed DGX Spark, the splash can stay active and keep systemd in `starting` after remote services are available.

Fleet's standalone recovery check recognizes this case on hosts in the discovered `dgx_spark` inventory group. It requires zero failed units, a successful job query, and `plymouth-quit-wait.service` as the only running job. Fleet accepts pending starts for the boot targets (`getty.target`, `multi-user.target`, `graphical.target`) and their observed console and runlevel units (`system-getty.slice`, `serial-getty@ttyS0.service`, `setvtrgb.service`, `systemd-update-utmp-runlevel.service`). Each must be waiting. Any other job blocks recovery.

Fleet logs the splash wait and continues the package and GPU checks. This check is read-only. Legacy Kubernetes resume checks still require the usual systemd health state.

Check the affected host over SSH:

```bash
systemctl is-system-running
systemctl --failed --no-pager
systemctl list-jobs --no-pager
systemctl status plymouth-quit-wait.service --no-pager
```

To end the current splash manually and let systemd finish booting:

```bash
sudo /usr/bin/plymouth quit
systemctl is-system-running
systemctl list-jobs --no-pager
```

The installed `plymouth-quit.service` uses the same command. It ends the splash for the current boot.

If the system remains in `starting`, inspect the remaining jobs. If it reports `degraded`, inspect the failed units. A recurring Plymouth wait needs separate investigation of the boot and display-manager configuration.

A restart or execution failure during automatic checks does not imply a new change occurred. The previous recovery state is preserved and the requested action is not automatically replayed. Healthy devices skip this extra check.
