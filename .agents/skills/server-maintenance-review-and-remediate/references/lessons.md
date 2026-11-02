# Verified lessons

These lessons come from source, regression tests, and bounded runtime reviews.
Their verification levels distinguish synthetic regressions from live evidence.
Recheck their applicability before using them.

## L007: Socket existence is not SSH agent readiness

- **Condition/mechanism:** SSH connections and host-key verification succeed,
  but shared-agent identity queries fail across SSH targets. Reachy daemon
  health is independent. A proxy listener and its bind-mounted socket can remain
  present after the dedicated host agent exits, producing false healthy status
  under the old socket-only probe.
- **Future check:** query identities on the host and from web with a timeout;
  inspect the recorded host PID and socket separately. Ask whether the reported
  restart includes `make start`, which recreates the agent and proxy. Do not
  infer bad host credentials or change host trust from this failure pattern.
- **Evidence:** `scripts/start.sh`; `ssh-agent-proxy/healthcheck.sh`;
  `docker-compose.yml`; `tests/test_ssh_agent_proxy.py`; README SSH troubleshooting.
- **Verification:** live read-only inspection found the dedicated host socket
  absent, its recorded PID gone, and a web identity query timing out despite
  healthy proxy status. The new probe detected this failure within three seconds;
  isolated regressions cover healthy, empty, disconnected, hung and incorrect
  identity sets. The proxy image builds. No repair/deployment was performed.
- **Limits/invalidation:** the reason the host agent terminated remains unknown.
  This detects failure and provides targeted recovery; it does not supervise or
  unlock a dead host agent. Revisit if agent ownership or forwarding changes.

## L001: Service scope differs from legacy CLI scope

- **Condition/mechanism:** older reviews describe Kubernetes prerequisites and
  retired catalog operations that no longer govern the standalone service.
- **Future check:** resolve the current route, dispatcher and playbook before
  restoring an old requirement or deleting an apparently unused playbook. Compare
  that catalog to both the canonical Fleet Help prompt and its UI guide.
  For new operations, trace request fields, runner allowlists, acceptance and
  queued eligibility, result types, UI consumers, and runtime dependencies.
  A standalone playbook and component do not establish a working service action.
- **Evidence:** `README.md` Common Operations and legacy Kubernetes sections;
  `backend/routers/operations.py`; `tests/test_simplified_operations.py`;
  `tests/test_reboot_workflow.py`; `tests/test_host_ip_check.py`;
  `tests/test_operation_review.py`; `nat/config.yml`; `docs/fleet-manager-ui.md`.
- **Verification:** source/history and regressions. The 2026-10-20 review found
  the prompt still described four actions and banned supported Reachy daemon
  restarts, while the guide's overview described six. Reconciled with the current
  eight-entry catalog; no fleet operation was executed. The later host-IP
  additions initially failed four API/runner tests because integration was
  absent, despite passing standalone Ansible fixtures. Regressions now cover
  registration, stale-fact exceptions, saved trust, verified results, and UI
  request scope; these are isolated checks, not live device verification.
- **Invalidate when:** service operating modes or supported CLI contracts change.

## L002: Slow indexing must not occupy fleet execution workers

- **Condition/mechanism:** embedding/index writes can block during provider
  outages; sharing the worker pool can stall unrelated fleet execution.
- **Future check:** inspect executor ownership and lock waits when latency
  coincides with index failures; preserve the dedicated index executor.
- **Evidence:** `backend/services/job_log_indexer.py`;
  `tests/test_followup_review.py::test_slow_indexing_cannot_starve_the_executor_used_for_fleet_work`;
  commit `3fcce1e`.
- **Verification:** implemented contract and existing concurrency regression;
  no live latency claim.
- **Invalidate when:** indexing or fleet execution moves to another queue/process.

## L003: Streaming and progress have different data contracts

- **Condition/mechanism:** repeated full job detail reads load logs/artifacts;
  disconnected SSE can leave a partial buffer after completion.
- **Future check:** active polling uses lightweight progress; completion fetches
  final evidence; late responses cannot overwrite a newer selection or result.
  Include mutation follow-ups such as cancellation, not only polling and SSE.
- **Evidence:** `backend/routers/jobs.py`; `frontend/src/views/JobHistory.vue`;
  `tests/test_followup_review.py`; `frontend/src/views/activity-flow.test.js`;
  commit `3fcce1e`.
- **Verification:** the 2026-10-20 mounted Vue regression reproduced cancellation
  of job A overwriting job B's selected details. It failed before adding the
  selection-generation guard and passed afterward. No browser or deployed
  performance measurement.
- **Invalidate when:** job detail/progress/stream APIs or client state ownership change.

## L004: Validate embeddings before changing a derived index

- **Condition/mechanism:** missing/duplicate indexes, nonfinite vectors, or
  inconsistent dimensions can misassociate documents or fail after rebuilding.
- **Future check:** exercise the batch contract in Python/NAT and Rust before
  index writes. Preserve SQL and job logs as authoritative evidence. Do not
  mistake validation before writes for an atomic index rebuild.
- **Evidence:** `nat/embedding_response.py`; `tools/dgx-doc-ingester/src/main.rs`;
  `tests/test_followup_review.py::test_invalid_embeddings_do_not_rebuild_or_delete_index`;
  commit `3fcce1e`.
- **Verification:** source/history and existing regressions; live provider and
  partial-write recovery remain separate checks.
- **Invalidate when:** provider response contracts or index replacement strategy change.

## L005: Redact shared job evidence before clipping or indexing

- **Condition/mechanism:** credential-name variations and unfinished private-key
  blocks bypassed the shared sanitizer used by fresh context and vector documents.
  Active logs can end before a key's closing marker.
- **Future check:** use sentinel credentials in summaries, artifacts, running
  logs and index documents. Cover `SECRET_KEY`, prefixed keys, Ansible SSH/become
  passwords, passphrases and incomplete key blocks. Preserve useful nonsensitive
  evidence. Treat filtering as pattern-based, not universal anonymization.
- **Evidence:** `backend/services/job_log_indexer.py::_sanitize_text`;
  `backend/services/job_context.py`;
  `tests/test_job_log_indexer.py::JobLogDocumentTests::test_job_documents_redact_key_and_ansible_credential_assignments`;
  `tests/test_job_context.py::JobContextTests::test_fresh_context_redacts_secret_keys_and_incomplete_private_key`.
- **Verification:** synthetic context/document regressions failed before the
  2026-10-20 fix and passed afterward. No live credential exposure was established.
  Existing indexed documents were not rewritten.
- **Invalidate when:** context ownership, credential formats, or ingestion paths
  change; check every consumer of the sanitizer again.

## L006: A multi-device job's status is not every device's outcome

- **Condition/mechanism:** mixed scans and other multi-device jobs can be partial
  or require recovery while some devices succeeded. The retrieval snapshot used
  the overall job status in per-host counts and details, and context documents
  omitted the durable per-device results when recaps were unavailable.
- **Future check:** match `Job.device_results` by exact hostname in snapshots and
  expose bounded, sanitized results in both fresh context and indexed documents.
  Preserve the overall job status separately. Missing historical per-device
  results mean unknown; do not infer success or failure from the group status.
- **Evidence:** `backend/services/job_log_indexer.py::build_fleet_snapshot_documents`;
  `backend/services/job_context.py::_detail`;
  `tests/test_job_log_indexer.py::JobLogDocumentTests::test_mixed_scan_snapshot_keeps_device_outcomes_separate_from_job_status`;
  `tests/test_job_log_indexer.py::JobLogDocumentTests::test_job_documents_include_redacted_per_device_results_without_a_recap`;
  `tests/test_job_context.py::JobContextTests::test_fresh_context_includes_redacted_device_outcomes_without_a_recap`.
- **Verification:** all three synthetic regressions failed before the fix and
  passed afterward. Read-only SQL inspection also found recent partial automatic
  scans with successful and unreachable devices, confirming applicability. No
  live Fleet Help answer or index refresh was performed; existing documents are
  unchanged until refreshed.
- **Invalidate when:** per-device result schemas, snapshot ownership, or historical
  job compatibility change.
