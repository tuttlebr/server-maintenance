# Fleet Manager UI Guide

This guide teaches Fleet Help how to explain the vendor-neutral Fleet Manager UI. Fleet Help is read-only: it may interpret documentation and recorded operation output, but it must never claim to inspect a device live or execute an operation.

## Information Architecture

- **Overview** summarizes reachability, devices needing attention, active jobs, and recent activity. GPU and robot metrics appear only when those device capabilities exist.
- **Devices** is the mixed-fleet inventory. Filter by status, type, vendor, or capability. Device types are server, workstation, edge, robot, and generic.
- **Operations** is the default page. It always shows six actions: Check for apt updates, Install apt updates, Clear container cache, Reboot nodes, Check storage, and Check GPU usage. Selection, review, progress, and results stay on this page.
- **Users** supports bulk Linux account additions and edits, manual rows or CSV import, and account observations. Operations also links here with the device selection preserved.
- **Activity** contains background and completed jobs, including target devices, status, recap, logs, errors, and compact structured results when an operation produces them.
- **Context** shows the current Fleet Help record count, manages uploaded text and Markdown sources, and runs context re-indexing.
- **Fleet Help** answers documentation and recorded-operation questions. It does not operate devices.

## Adding Devices

Use **Devices → Add device**. The flow is connection, details, discovery, and review.

For Linux over SSH, enter an inventory-safe device name, endpoint, SSH user, and authentication details. Fleet Manager retrieves the ED25519 host fingerprint. Compare it through the device console or another trusted channel before approving it. The application rechecks the key, verifies authentication, and only then stores the device.

For Reachy Mini Wireless, provide the network endpoint and daemon port. Discovery calls read-only state, daemon-status, and update-availability endpoints. The daemon integration does not expose movement, motors, camera, audio, or general app controls. Reachy's local daemon connection is not identity-verified, so enroll robots only on a trusted management network.

Use **Import CSV** for larger fleets. The importer parses rows locally, discovers every device, shows per-row failures and SSH fingerprints, requires explicit verification of all listed fingerprints, and enrolls only ready rows. Required columns are `name`, `endpoint`, and `transport`; SSH rows also require `ssh_user`.

Use **Download CSV** to export all devices in the importer's column format. Inventory names and connection settings are included. Stored SSH, sudo, and one-time bootstrap passwords are excluded, so add the password back to password-authenticated SSH rows before importing them.

Discovery assigns a general device kind and explicit capabilities. Failure to identify a vendor or product model does not prevent a reachable Linux device from being managed as generic.

## Device Details

Device Summary shows identity, connection, reachability, and last discovery. Hardware and Software omit facts that do not apply instead of displaying empty placeholders. Context stores operator-provided key/value attributes and links to documentation associated with that device. Operations lists the device's discovered capabilities and links to the capability-filtered Operations experience.


Scanning an SSH device runs the portable facts playbook. It probes Linux, storage, architecture, system and motherboard identity, BIOS, CPU topology, network interfaces, virtualization, NVIDIA GPU availability, Fabric Manager, MIG, and local Kubernetes membership indicators without querying the cluster or assuming capabilities from a product name. Scanning Reachy checks daemon connectivity and state without moving the robot. A scan refreshes discovered facts but does not replace manual attributes.

## Managing Context

Use **Context** to upload UTF-8 `.txt`, `.md`, or `.markdown` documents. A source may apply to the fleet generally or be associated with one device. For example, associate a motherboard owner's manual with `daedalus-02` and add its exact motherboard model under **Devices → daedalus-02 → Context**. The generated index source includes the device name, current discovered identity, manual attributes, and document content together.

Uploads, deletions, and attribute edits are staged changes. Select **Re-index context** to rebuild `fleet_docs`. The page reports the current indexed record count, source counts, phase, progress, completion time, and errors. Removing a document does not remove its old vector records until the next successful re-index.

## Operations and Safety

Select devices once in the left panel. **Check now** refreshes apt metadata and reports candidate packages without installing them. **Review & install** uses the latest complete successful check for the exact selection, or runs a new check first. Checks expire after 30 minutes. Review package details inline, then confirm the exact device list with one button. No typed names, preview dropdown, or separate Activity visit is required.

**Clear cache…** asks once before clearing unused Docker images/build cache and unused containerd images through nerdctl. It keeps containers, volumes, and networks. Runtime details show namespace results and explicitly identify unavailable BuildKit cache or failed runtimes. Cleanup uses the privileged system runtime configuration, not every user's rootless runtime.

**Reboot…** opens one confirmation for the selected nodes. It always restarts them, one at a time, even without a reboot-required flag or with pending recovery. It skips preflight health checks and node draining, waits for reboot completion and SSH access, then refreshes facts. Active device reservations still prevent overlapping operations. Failures remain visible per device.

**Check storage** runs immediately on the selected SSH nodes. It shows used, available, total capacity, and percentage used for the filesystem containing `/home` (often `/`) and every mount target in `/etc/fstab`, including small and bind mounts. Swap is excluded. Unmounted or inaccessible entries show unavailable capacity instead of the parent filesystem's free space. Optional, noauto, and pending automount entries are labeled; nothing is mounted and no directory tree scan is run. Results use one home-capacity table and group network mounts by their exact source, with each node’s state available by expanding the group. Capacity is never summed across nodes. Identical fstab observations collapse with a count; conflicting entries stay separate. Healthy boot and mounted virtual filesystems appear under All mount details, while low-space and missing-required-mount issues stay visible. Successful per-node status repeats and repeated notes are omitted. Storage technical logs are collapsed in Activity, and new runs omit verbose JSON dumps.

**Check GPUs** runs immediately on selected GPU-capable SSH nodes using `nvidia-smi`. Results show per-GPU utilization and memory, compute/graphics processes, PIDs, effective Linux owners, executable paths when readable, and available container/pod context. Container owner labels are hints, separate from the Linux owner; a pod namespace is not treated as a person. Unsupported utilization or memory (including MIG and unified-memory systems) stays unavailable. Missing process information is not interpreted as a free GPU. These are timestamped snapshots, not continuous monitoring or per-process utilization percentages. Both checks preserve per-device failures and show detailed results in Operations and Activity.

The maintenance catalog exposes these six actions. Bulk account management is available separately under Users. Driver/firmware updates, service control, and Reachy mutations are retired from the service. Legacy CLI playbooks and historical job results do not mean those controls are still available in the UI.

APT actions require a discovered Debian-family SSH device. Cleanup requires a discovered container runtime. The backend checks every selected device; the UI never silently excludes an incompatible device. All devices use standalone maintenance. Installation and recovery verification require no maintenance-mode configuration, cluster API access, or node draining. After an incomplete change, installs and cleanup automatically check host health, refresh device details, and continue in the same job. If a check fails, the requested action does not start and the device error appears inline. No manual Verify step is required. Running jobs reserve their devices throughout both checks and changes. Stale dashboard facts alone no longer require a separate scan before maintenance.

Blockers appear inline with device settings and deselection links. Recovery checks run automatically inside installs and cleanup. Reboot has no recovery prerequisite; previously recorded health issues are checked before a later install or cleanup. Failed pre-mutation package checks do not create recovery locks; changes that started and could not be verified still do.

Results show per-device outcomes, available packages, reboot requirements, runtime cleanup details, storage capacity and mount states, GPU processes and owners, and the technical log. Progress reconnects automatically after transient polling errors. If starting a request loses its response, **Reconnect to request** reuses the original request key. It never automatically repeats an accepted mutation. **Activity** retains historical results. A successful historical job is not proof of current live health.

**Partial** means some, but not all, targeted devices completed successfully. Filter Activity by **Partial**, or open a run to review each device's outcome. Partial runs also appear under **Adverse outcomes**. Cancellation and **Health check pending** take precedence when execution was cancelled or a change requires an automatic health check before further changes.

## Fleet Help Evidence Rules

Fleet Help receives fresh activity evidence with each question and can search completed operation logs for additional history when needed. Results are time-stamped historical observations. Integration documentation covers products and procedures; it does not establish a device's current state.

If a required fact has not been recorded, say which evidence is missing and direct the user to the narrowest eligible operation that collects it. Carry device names and scope forward in follow-up questions.
## User management

Use **Users** or the Operations **Manage users** link. Select devices and choose **Add users** or **Edit users**. Enter rows or upload a UTF-8 CSV, then review once and run. Progress and per-device errors stay inline; ambiguous network retries reconnect to the same request.

Download a template for the selected mode. Columns are `username,full_name,email,groups,shell`. Add requires full_name and either username or email; the username defaults to the email local part. Edit requires username and at least one changed field. Blank edit fields preserve their current values; groups append without removing memberships. Quote fields containing commas. Upload replaces the current mode's editable rows. Invalid files show row errors and launch no work. Limits: 1 MB, 500 users, and 200 explicit devices. Legacy two-column full_name/email add files also work without a header.

Add creates missing accounts only, using system home defaults and `/bin/bash`. Password login is locked unless an initial password is supplied (minimum 12 characters, changed at first login). Edit never creates missing users. Full names, groups, and shells are remote account attributes; email is Fleet Manager metadata. Platform, account, and shell prerequisites are checked live. Pending health checks run automatically within the same reserved job, without a separate Scan or Verify step or node draining.

The **Accounts** tab shows observed state per selected device. **Refresh accounts** discovers existing users. Select users and choose **Edit selected users** to populate the edit rows.
