# Recovery checks

**Verify recovery** checks mounts, systemd, Debian package configuration, and NVIDIA GPU access where applicable. Kubernetes nodes also require cluster health checks. Successful verification refreshes device facts and clears the recovery requirement. Verification does not repair services or change node scheduling.

Recovery verification works before a maintenance mode is configured, including on existing devices whose mode is `unknown`. It discovers Kubernetes membership using local files, controller node identity, and prior scan evidence. Any known or configured Kubernetes member still requires an accessible API, a unique matching node, and readiness verification. A missing kubeconfig or unmatched node produces an actionable failure rather than silently skipping cluster checks. Standalone hosts can verify health without cluster access.

Verification leaves the saved maintenance mode unchanged. Before rebooting, updating, or making other disruptive changes, select **Standalone host** or **Kubernetes node** in **Devices → Edit device**. Those operations retain their explicit maintenance policy and drain safeguards. A failed or incomplete follow-up scan keeps the affected device unverified and cannot clear its recovery requirement, even if a scan report was written before the failure.

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

This is the command used by the installed `plymouth-quit.service`. It ends the current splash process without disabling services or changing future boot configuration. Allow pending jobs to finish, then rerun **Verify recovery**.

If the system remains in `starting`, inspect the remaining jobs. If it reports `degraded`, inspect the failed units. A recurring Plymouth wait needs separate investigation of the boot and display-manager configuration.
