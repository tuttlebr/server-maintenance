# Reliability implementation

Implemented 2026-09-20, following [the operations review](operations-review.md). The earlier review is a historical baseline; this document describes the resulting behavior.

| Area | Implemented behavior |
| --- | --- |
| Account scope | Every UI action snapshots explicit devices and account names into a confirmation. Implicit fleet-wide account requests and empty bulk-reset account lists are rejected. Provisioning preserves existing account configuration and uses system home defaults. |
| Privilege state | Groups, shell, the managed passwordless grant, effective `sudo -l` evidence, observation time, and verification state are stored per account/device. Legacy global flags are not presented as observations. Partial results update only the hosts actually observed. Revocation removes only the managed grant line. |
| Execution | SQL device reservations reject overlapping jobs and connection changes. Request keys deduplicate accepted Ansible and remote mutation requests. Reachy health/log collection and fleet scans are tracked jobs under the same reservations and concurrency limit. A process supervisor ties the entire Ansible/SSH process group to the web executor's lifetime. Secret FIFO handoff is bounded and does not expose credentials in process arguments. |
| Interruptions | Queued jobs are cancelled after restart; interrupted inspections fail; interrupted changes require recovery. Changes are never automatically replayed. Running changes cannot be cancelled through the UI; queued Ansible jobs and running Ansible inspections can. Recovery state blocks further mutations. |
| Kubernetes | Maintenance requires explicit standalone/Kubernetes mode. Standalone mode rejects local membership evidence. Drains respect disruption budgets, unmanaged-pod protections, and local-volume protections. Recovery artifacts preserve context, node UID, original scheduling state, and phase. Failed maintenance stays cordoned. Automatic restoration and explicit resume require host health and a Ready node without pressure conditions. Originally cordoned nodes remain cordoned. |
| Recovery | Verify recovery checks filesystem configuration and required mounts, systemd health, Debian package configuration, GPU response when applicable, and Kubernetes readiness, then refreshes facts. It does not roll back changes or uncordon nodes. Resume is a separate explicit action. Reachy recovery checks the recorded remote job ID and daemon health without repeating the change. |
| Eligibility and freshness | Catalog and API gates require the relevant discovered OS, service manager, driver package and maintenance mode. Blocked devices have actionable reasons. Facts older than an hour or invalidated by a mutation/failed scan are marked stale. Successful mutations refresh facts before releasing their devices; missing verification results require recovery. |
| Packages | A successful preview for exactly the same devices is required and expires after 30 minutes. Proposed versions and transactions are visible in Activity. Apply rechecks the fingerprint before and after drain and pins the proposed package versions. Debian removals and DNF dependency erasure are blocked. |
| Services | Inspect systemd units, start/stop/restart one existing unit, verify the observed result, and inspect structured service states in Activity. Common SSH/network/cluster/runtime services and aliases are protected. Kubernetes hosts use the same maintenance safeguards. |
| Fleet visibility | Activity shows per-device outcomes, verification phase, recovery status, cancellation, and structured results. Scan and launch actions link to their jobs. Fleet attention counts use the complete set; active job counts come from a dedicated full-count query rather than recent history. |

## Rollout

The normal container startup runs Alembic migration `0006_operation_reliability`. Existing devices start with unverified facts and unknown maintenance mode. Scan them, configure the appropriate mode in **Devices → Edit device**, and inspect accounts before relying on their access state. Existing global privilege flags are deliberately not copied into observed per-device privileges.

Run one web worker/executor per data directory. An exclusive process lease rejects competing workers and remains held by a surviving child supervisor until its process group has stopped. This is a supervised single-executor deployment, not a distributed task queue.

## Validation and boundaries

Validation uses isolated databases, local subprocesses, a fake Kubernetes API, and a read-only UI fixture. No maintenance was executed on registered servers, and the running deployment was not changed.

Final checks: 168 backend tests and 16 subtests passed, all 9 frontend tests passed, and the production frontend build succeeded. Ansible lint passed all 46 playbook/task files, including syntax validation. Two existing Alembic configuration deprecation warnings remain.

Regression coverage includes database migration, restart reconciliation, reservation conflicts, idempotency, queued cancellation, per-host account reconciliation, partial mutation failure, missing post-operation reports, failed recovery, remote job-ID recovery, scope/freshness/platform guards, exact package preview targets and expiration, supervisor EOF, and early subprocess failure before FIFO handoff. Ansible integration tests execute the production scheduling flow with injected drain, maintenance, readiness, and host-health failures. Additional tests exercise the actual Ansible package-version parsing expressions.

Browser checks cover per-device privilege differences, explicit account and service confirmations, blocked operation inputs, structured package previews, and the preview-to-apply link. Evidence: [account confirmation](operations-evidence/08-scoped-account-confirmation.png), [package results](operations-evidence/09-package-preview-results.png).

Recovery checks establish the documented host/node conditions, not application-specific correctness or rollback. A detached remote package process may outlive an SSH connection; recovery stays explicit. A Reachy request interrupted before the daemon acknowledges a remote job ID cannot be automatically certified and requires daemon-side investigation. Package availability, repository contents, site-specific services, and real cluster RBAC still need a staged validation on representative devices before production rollout.

The subsequent full UI review should still address catalog navigation at fleet scale, shared target selection, richer service-log workflows, and responsive fleet tables.
