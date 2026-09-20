# Fleet Manager UI Guide

This guide teaches Fleet Help how to explain the vendor-neutral Fleet Manager UI. Fleet Help is read-only: it may interpret documentation and recorded operation output, but it must never claim to inspect a device live or execute an operation.

## Information Architecture

- **Overview** summarizes reachability, devices needing attention, active jobs, and recent activity. GPU and robot metrics appear only when those device capabilities exist.
- **Devices** is the mixed-fleet inventory. Filter by status, type, vendor, or capability. Device types are server, workstation, edge, robot, and generic.
- **Operations** shows only actions supported by at least one current device. Operators select eligible devices, review impact, confirm, and then monitor Activity.
- **Access** manages Linux accounts on devices with `users.manage`. Robots and devices without Linux account management are excluded.
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

A Reachy device also shows **Enable app reset**. This separate setup reads its ED25519 SSH host key, requires out-of-band fingerprint approval, and verifies SSH authentication before adding the reset capability. The configured Reachy remains excluded from general Linux operations.

Scanning an SSH device runs the portable facts playbook. It probes Linux, storage, architecture, system and motherboard identity, BIOS, CPU topology, network interfaces, virtualization, NVIDIA GPU availability, Fabric Manager, MIG, and Kubernetes without assuming those capabilities from a product name. Scanning Reachy checks daemon connectivity and state without moving the robot. A scan refreshes discovered facts but does not replace manual attributes.

## Managing Context

Use **Context** to upload UTF-8 `.txt`, `.md`, or `.markdown` documents. A source may apply to the fleet generally or be associated with one device. For example, associate a motherboard owner's manual with `daedalus-02` and add its exact motherboard model under **Devices → daedalus-02 → Context**. The generated index source includes the device name, current discovered identity, manual attributes, and document content together.

Uploads, deletions, and attribute edits are staged changes. Select **Re-index context** to rebuild `fleet_docs`. The page reports the current indexed record count, source counts, phase, progress, completion time, and errors. Removing a document does not remove its old vector records until the next successful re-index.

## Operations and Safety

Operation eligibility is enforced twice: the UI shows only eligible targets, and the backend rejects unsupported device IDs. A device name or vendor never grants an operation by itself.

Low-impact observations include device scan, maintenance assessment, storage analysis, GPU usage, firmware inventory, Fabric Manager status, MIG status, Kubernetes readiness, Reachy health, and bounded Reachy daemon-log collection. System package updates, host bootstrap, firmware updates, reboots, driver updates, cleanup, Reachy software updates, Reachy daemon restarts, and Reachy app reset require stronger confirmation. Driver updates stay on the installed driver branch; general operating-system updates are a separate action. Reachy software operations use documented daemon endpoints and still never send motion commands.

**Reset Reachy apps** requires typing the selected target names. Its playbook refuses unverified host types, fixes the deletion target to `/venvs/apps_venv`, removes that environment idempotently, and reminds the operator that apps must be reinstalled. Its concise result is represented in Activity through the Ansible recap and log; it does not need a separate visual result card.

After starting an operation, use **Activity** to monitor progress and review output. GPU, storage, maintenance-assessment, and driver jobs show compact result cards above the full Ansible log. A successful historical job is not proof of current live health.

## Fleet Help Evidence Rules

Always search recorded operation logs for questions about the user's fleet. Treat results as time-stamped historical observations. Use integration documentation for product or procedure questions, and do not represent documentation as the user's current device state.

If a required fact has not been recorded, say which evidence is missing and direct the user to the narrowest eligible operation that collects it. Carry device names and scope forward in follow-up questions.
