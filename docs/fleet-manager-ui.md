# Fleet Manager UI Guide

This guide teaches Fleet Help how to explain the vendor-neutral Fleet Manager UI. Fleet Help is read-only: it may interpret documentation and recorded operation output, but it must never claim to inspect a device live or execute an operation.

## Information Architecture

- **Overview** summarizes reachability, devices needing attention, active jobs, and recent activity. GPU and robot metrics appear only when those device capabilities exist.
- **Devices** is the mixed-fleet inventory. Filter by status, type, vendor, or capability. Device types are server, workstation, edge, robot, and generic.
- **Operations** shows only actions supported by at least one current device. Operators select eligible devices, review impact, confirm, and then monitor Activity.
- **Access** manages Linux accounts on devices with `users.manage`. Robots and devices without Linux account management are excluded.
- **Activity** contains background and completed jobs, including target devices, status, recap, logs, and errors.
- **Fleet Help** answers documentation and recorded-operation questions. It does not operate devices.

## Adding Devices

Use **Devices → Add device**. The flow is connection, details, discovery, and review.

For Linux over SSH, enter an inventory-safe device name, endpoint, SSH user, and authentication details. Fleet Manager retrieves the ED25519 host fingerprint. Compare it through the device console or another trusted channel before approving it. The application rechecks the key, verifies authentication, and only then stores the device.

For Reachy Mini Wireless, provide the network endpoint and daemon port. Discovery calls read-only state, daemon-status, and update-availability endpoints. The integration does not expose movement, motors, camera, audio, or app controls. Reachy's local daemon connection is not identity-verified, so enroll robots only on a trusted management network.

Use **Import CSV** for larger fleets. The importer parses rows locally, discovers every device, shows per-row failures and SSH fingerprints, requires explicit verification of all listed fingerprints, and enrolls only ready rows. Required columns are `name`, `endpoint`, and `transport`; SSH rows also require `ssh_user`.

Discovery assigns a general device kind and explicit capabilities. Failure to identify a vendor or product model does not prevent a reachable Linux device from being managed as generic.

## Device Details

Device Summary shows identity, connection, reachability, and last discovery. Hardware and Software omit facts that do not apply instead of displaying empty placeholders. Operations lists the device's discovered capabilities and links to the capability-filtered Operations experience.

Scanning an SSH device runs the portable facts playbook. It probes Linux, storage, architecture, vendor and product facts, NVIDIA GPU availability, Fabric Manager, MIG, and Kubernetes without assuming those capabilities from a product name. Scanning Reachy checks daemon connectivity and state without moving the robot.

## Operations and Safety

Operation eligibility is enforced twice: the UI shows only eligible targets, and the backend rejects unsupported device IDs. A device name or vendor never grants an operation by itself.

Low-impact observations include device scan, storage analysis, GPU usage, Fabric Manager status, MIG status, Kubernetes readiness, Reachy health, and bounded Reachy daemon-log collection. Reboots, driver updates, cleanup, Reachy software updates, and Reachy daemon restarts require stronger confirmation. Reachy software operations use documented daemon endpoints and still never send motion commands.

After starting an operation, use **Activity** to monitor progress and review output. A successful historical job is not proof of current live health.

## Fleet Help Evidence Rules

Always search recorded operation logs for questions about the user's fleet. Treat results as time-stamped historical observations. Use integration documentation for product or procedure questions, and do not represent documentation as the user's current device state.

If a required fact has not been recorded, say which evidence is missing and direct the user to the narrowest eligible operation that collects it. Carry device names and scope forward in follow-up questions.
