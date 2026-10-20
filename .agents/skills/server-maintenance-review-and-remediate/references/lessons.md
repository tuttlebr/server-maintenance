# Verified lessons

These lessons come from source, regression tests, and bounded runtime reviews.
Their verification levels distinguish synthetic regressions from live evidence.
Recheck their applicability before using them.

## L001: Service scope differs from legacy CLI scope

- **Condition/mechanism:** older reviews describe Kubernetes prerequisites and
  retired catalog operations that no longer govern the standalone service.
- **Future check:** resolve the current route, dispatcher and playbook before
  restoring an old requirement or deleting an apparently unused playbook. Compare
  that catalog to both the canonical Fleet Help prompt and its UI guide.
- **Evidence:** `README.md` Common Operations and legacy Kubernetes sections;
  `backend/routers/operations.py`; `tests/test_simplified_operations.py`;
  `tests/test_reboot_workflow.py`; `nat/config.yml`; `docs/fleet-manager-ui.md`.
- **Verification:** source/history and regressions. The 2026-10-20 review found
  the prompt still described four actions and banned supported Reachy daemon
  restarts, while the guide's overview described six. Reconciled with the current
  eight-entry catalog; no fleet operation was executed.
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
