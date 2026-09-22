# Recovery checks

**Verify recovery** checks mounts, systemd, Debian package configuration, and NVIDIA GPU access where applicable. Kubernetes nodes also require cluster health checks. Successful verification refreshes device facts and clears the recovery requirement. Verification does not repair services or change node scheduling.

SSH access alone does not establish that boot has completed. The systemd check requires a successful `systemctl is-system-running` result of `running` and a successful query with no failed units. Other states, including `starting`, `degraded`, and `maintenance`, keep recovery blocked.

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
