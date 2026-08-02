# Fleet Manager UI Guide

This guide teaches DGX Help how to help users operate the Fleet Manager web UI. Use it for questions about navigation, where to click, what each page does, and how to monitor actions after they start.

DGX Help should guide users through the UI and explain consequences, but it should not claim to execute destructive actions itself. For actions that affect hosts, users, drivers, reboots, Docker cleanup, package updates, or documentation indexing, tell the user which page and control to use and remind them to review the confirmation dialog and Job History.

## Main Navigation

The main navigation bar contains Dashboard, Users, Drivers, Networking, Maintenance, Jobs, Active, and Sign Out.

Dashboard is the fleet landing page. Use it to review host cards, add hosts, scan hosts, and open a host detail page.

Users opens User Management. Use it for provisioning users, importing users from CSV, resetting passwords, managing sudo access, and removing managed users.

Drivers opens Driver Management. Use it to review driver versions and start driver upgrades. Firmware inventory and updates live on Maintenance.

Networking opens Fabric Manager controls and networking status. Fabric Manager actions only apply to DGX Workstation hosts with NVSwitch support. DGX Spark does not support Fabric Manager.

Maintenance opens System Maintenance. Use it for disk usage, reboot required, storage analysis, GPU usage, package updates, Docker cleanup, preflight checks, diagnostics, host bootstrap, firmware actions, drain/resume, MIG controls, and the DGX Help Documentation Index.

Maintenance Targets sets the host scope for host-scoped maintenance actions. All Hosts uses each playbook's supported host group. Selected Hosts can target one machine or any subset. Firmware support is detected by the playbook at runtime, GPU usage is limited to known NVIDIA GPU nodes, and MIG actions are limited to DGX Workstation hosts.

Jobs opens Job History. Use it to inspect playbook output, status, timing, and AI error analysis.

Active opens the active jobs tray. It shows currently running jobs and links to Job History.

## Dashboard Workflows

Use Dashboard to understand fleet health at a glance. Host cards show status, machine type, driver version, disk usage, and other summary information. Click a host card or hostname to open Host Detail.

To add a host, use the add host controls on Dashboard. Enter the hostname or address, the existing remote SSH username, and the correct machine type group. Choose Unknown / Auto-detect when the platform class is not known. Unknown hosts are not assumed to have GPUs. The container's local `fleet` user is not the remote SSH account.

For dedicated-key authentication, the fleet SSH agent must be healthy. If its public key is already authorized for the remote account, leave the one-time bootstrap password blank. Otherwise provide the remote account password so Fleet Manager can install the public key; this password is not stored.

Select **Verify SSH & Add** to retrieve the host's ED25519 fingerprint. Compare it through the host console or another trusted channel before approving it. Fleet Manager rechecks the approved key, verifies authentication, and only then saves the host. Bulk CSV import follows the same workflow for every row. After enrollment succeeds, run a scan so the system gathers facts and populates driver, disk, GPU, and reboot status.

To refresh host facts, use scan on an individual host or scan all hosts from Dashboard when available. Scans start background jobs. Tell users to check the Active jobs tray or Job History if a scan does not update the card immediately.

## Host Detail Workflows

Host Detail is for single-host operations. Use it when the user asks about one specific host, wants to edit SSH connection settings, scan one host, delete one host, or start a driver upgrade on one host.

After starting a Host Detail action, the UI creates a job. If the card still shows old data, wait for the job to complete and refresh or rescan the host.

Deleting a host removes it from Fleet Manager inventory. It does not describe wiping the remote machine. Users should confirm the hostname before deleting.

## User Management Workflows

The Users page has Add Users and Manage Users tabs.

Use Add Users to provision new accounts. Users can be entered manually with full name and email, or imported with CSV. Select one or more target hosts before clicking Provision Users. Provisioning creates remote user accounts, home directories, SSH configuration, and related managed-user records.

For CSV import, use columns that provide names and email addresses. Review the parsed preview before provisioning. If a user is missing from the preview, fix the CSV before starting the job.

Use Manage Users to search existing managed users, change a single user password, reset passwords in bulk, add a user to sudoers, remove a user from sudoers, or remove a managed user. Password resets and removals use confirmation dialogs because they affect multiple hosts.

Removing a managed user preserves the home directory unless the UI explicitly says otherwise. Users should review the confirmation text and then check Job History for the remote command result.

## Driver Management Workflows

Use Drivers to review driver status across the fleet and start upgrades. Select target hosts and choose the desired upgrade mode or target version shown in the UI. Driver upgrades run as jobs and can take several minutes.

Driver upgrades are high-impact maintenance actions. Tell users to schedule an appropriate maintenance window, read the confirmation dialog, and monitor Job History. Major version mode installs a target `nvidia-driver-<branch>` package. Firmware updates are separate Maintenance actions.

For a single host, users can also open Host Detail and click Upgrade Drivers for that host.

## Networking And Fabric Manager

Use Networking to view Fabric Manager state and start, stop, restart, or check Fabric Manager on supported hosts.

Fabric Manager is only supported on DGX Workstation hosts that have NVSwitch. If the UI shows Fabric Manager as unsupported or disabled for DGX Spark, that is expected. DGX Spark is a single-GPU desktop system and does not use multi-GPU NVSwitch Fabric Manager controls.

After starting a Fabric Manager action, check the active job and Job History for status and output.

## Maintenance Workflows

The Maintenance page contains sections for Targets, Disk, Reboot, Storage, GPU, Actions, and Docs.

Disk shows current root and RAID usage by host. Use it for quick capacity checks.

Reboot Required lists hosts that report a pending reboot. Reboot All is a high-blast-radius action and reboots one host at a time. Targeted Reboot follows the maintenance target selection and can force-reboot one host, all hosts, or a subset. The reboot playbook verifies fstab syntax and confirms that automatically mounted fstab targets return after reboot. Users should confirm hostnames and expect temporary loss of access.

Storage Analysis runs a deeper storage report for the selected maintenance targets and shows mount usage and large entries. Start Analyze Storage, then wait for the inline job status or inspect Job History.

GPU Usage runs GPU utilization collection for the selected maintenance targets. Start Analyze GPU Usage, then review the resulting per-host report or Job History.

Package Update starts rolling package updates on the selected maintenance targets. Package updates can change system state and may require a reboot afterward. Docker cleanup is separate and also follows the maintenance target selection.

Docker Cleanup prunes unused Docker images, build cache, networks, and containerd images across hosts. It does not remove running containers or volumes according to the UI confirmation text, but users should still review the confirmation before starting.

Preflight runs read-only maintenance readiness checks. Use it before package updates, driver upgrades, firmware updates, reboots, or MIG changes. It reports apt or dpkg activity, disk pressure, reboot-required state, active GPU processes, GPU containers, Kubernetes schedulability when available, and DGX Workstation service health.

Health Diagnostics collects deeper host output for troubleshooting, including nvidia-smi, GPU ECC and thermal data, Fabric Manager, DCGM, NVSM, IB status, failed systemd units, critical journal entries, and storage summaries. It is diagnostic and should be reviewed in Job History.

Host Bootstrap runs common groups, admin sudo setup, Docker and NVIDIA Container Toolkit installation, and a host scan. Use it for onboarding a newly added host after SSH access is working.

Firmware Inventory lists available firmware information for the selected maintenance targets. Firmware Update applies available firmware updates independently from driver upgrades and may require a later reboot.

Drain / Resume checks active GPU work and runs Kubernetes cordon, drain, or uncordon when kubectl is configured on the target host. If Kubernetes is not configured, the job reports that status rather than inventing cluster state.

MIG actions query, enable, or disable MIG mode on DGX Workstation hosts. Enable and disable refuse to run when active GPU processes are detected.

The Docs section contains DGX Help Documentation Index. Click Reindex Documentation to crawl URLs from `docs/urls.txt`, include local Markdown guidance from `docs/*.md`, convert content to Markdown, rebuild the Milvus collection, and re-embed documentation using the configured embedding model. DGX Help may have incomplete answers while reindexing runs.

## Job History And Troubleshooting

Use Jobs to see every background job, including scans, user management, driver upgrades, reboots, storage analysis, GPU usage, Docker cleanup, package updates, preflight checks, diagnostics, bootstrap, firmware actions, drain/resume, MIG actions, and documentation reindexing.

Open a job to view status and output. For failed jobs, use AI analysis when available to summarize likely causes from the job output. If a user asks why an operation failed, ask for the job ID or direct them to the failed job in Job History.

If a UI action appears stuck, check the Active jobs tray first, then Job History. A browser refresh does not stop a backend job that has already started.

## DGX Help Behavior

DGX Help should answer DGX hardware and documentation questions from the indexed documentation and answer UI usage questions from this guide.

When a user asks how to perform an action in the tool, answer with the page name, the control or section name, and what to verify after starting the action. Example: "Go to Maintenance, open the Docs section, click Reindex Documentation, confirm the dialog, then watch the progress card or Jobs."

When a user asks whether DGX Help can perform an action for them, explain that DGX Help can guide the workflow but the user must start destructive or operational actions from the UI confirmation dialog.

When a user asks about current UI state, job status, selected hosts, or page-specific context that is not included in the chat, say what page to check. Do not invent live state.
