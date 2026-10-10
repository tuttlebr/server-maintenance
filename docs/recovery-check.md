# Automatic health checks

At startup, Fleet repairs recovery flags left by older runners when the completed job log proves the attempt stopped before making changes. This covers rejected package previews, initial SSH failures, unavailable container runtimes before pruning, and devices never reached after those preflight failures. Activity retains the failed attempt and records why its recovery flag was cleared. No remote command runs during this repair.

A zero-change recap alone is not sufficient evidence: failed Kubernetes drains can already have changed scheduling. Interrupted jobs, timeouts, incomplete logs, and evidence of a mutation retain their recovery requirements. Package checks and explicit reboots remain available. Reboot skips preflight verification and waits for the node to return; this alone does not prove every earlier host-health issue is resolved. The next install or cleanup automatically verifies affected hosts before making changes.

The automatic check treats all devices as standalone hosts and checks mounts, systemd, Debian package configuration, and NVIDIA GPU access where applicable. It requires no Kubernetes access, maintenance-mode configuration, or node readiness check. It runs within the requested action under the same device reservation. Successful verification refreshes device facts, clears the recovery requirement, and continues the requested action. If any selected device fails, no part of the requested action starts; the job shows the specific error and can be retried after the issue is resolved. Verification does not repair services or change node scheduling.

Existing inventory metadata does not change this policy. A failed or incomplete follow-up scan keeps the affected device unverified and cannot clear its recovery requirement, even if a scan report was written before the failure. Facts scans inspect local membership files for inventory only; they do not query a cluster API.

SSH access alone does not establish that boot has completed. The systemd check requires `running` (rc=0), or `degraded` (rc=1) when every failed unit is explicitly ignored as non-critical. By default, only `motd-news.service` is ignored. The job reports ignored failures without resetting, disabling, or masking services. All other failed units, state or failed-unit query errors, unexplained degradation, and states such as `starting` or `maintenance` keep recovery blocked.

Set `fleet_systemd_ignored_units` in inventory/group/host variables to replace the default list of exact unit names. Set it to `[]` to require zero failed units. An ignored MOTD failure cannot hide another service failure or an incomplete boot.

Mount validation ignores fstab comments, blank lines, swap, and entries with `noauto`, `nofail`, or `x-systemd.automount`. Comment detection works with the older `mawk` shipped on Jetson devices, including indented comments. Mandatory mounts and fstab validation errors still block recovery.

When this check fails, the job output includes the system state, command return codes, failed units, pending jobs, and query errors. An empty failed-unit list does not mean that boot has completed.

## DGX Spark waiting for the boot splash

On the two Sparks inspected during this failure, systemd reported `starting` with zero failed units. `plymouth-quit-wait.service` remained in `activating` state. Its pending start job held up `multi-user.target` and other boot jobs, although SSH and the display manager were active.

Check the affected host over SSH:

```bash
systemctl is-system-running
systemctl --failed --no-pager
systemctl list-jobs --no-pager
systemctl status plymouth-quit-wait.service --no-pager
```

If these checks confirm the same stalled Plymouth wait, end the boot splash:

```bash
sudo /usr/bin/plymouth quit
systemctl is-system-running
systemctl list-jobs --no-pager
```

This is the command used by the installed `plymouth-quit.service`. It ends the current splash process without disabling services or changing future boot configuration. Allow pending jobs to finish, then retry the intended operation; its health check runs automatically.

If the system remains in `starting`, inspect the remaining jobs. If it reports `degraded`, inspect the failed units. A recurring Plymouth wait needs separate investigation of the boot and display-manager configuration.

A restart or execution failure during automatic checks does not imply a new change occurred. The previous recovery state is preserved and the requested action is not automatically replayed. Healthy devices skip this extra check.
