# Repository guide

Paths are relative to the checkout. Confirm this map against current code and
CI on every review; update it when ownership or commands move.

## Contracts and entry points

| Surface | Read | Review focus |
| --- | --- | --- |
| Product behavior | `README.md`, `docs/fleet-manager-ui.md`, `docs/recovery-check.md` | Current service catalog, confirmations, standalone policy, recovery and observation age |
| API and identity | `backend/main.py`, `backend/auth.py`, `backend/schemas.py`, `backend/routers/` | Authentication, validation, explicit target scope and error semantics |
| Execution | `backend/services/ansible_runner.py`, `backend/services/execution_state.py`, `backend/services/process_supervisor.py`, `backend/services/recovery_state.py` | Durable reservations, single executor, idempotency, interruption and per-host verification |
| Device and account evidence | `backend/services/device_discovery.py`, `backend/services/account_state.py`, `backend/services/job_results.py`, `backend/capabilities.py` | Missing/partial observations, correct eligibility, user discovery and stale state |
| Host operations | `playbooks/`, `playbooks/tasks/`, `playbooks/files/`, `backend/services/inventory_writer.py` | Actual Ansible dispatch and report contracts; legacy CLI compatibility |
| Persistence | `backend/models.py`, `backend/database.py`, `backend/migrations/` | Database compatibility, startup reconciliation, authoritative job evidence |
| Frontend | `frontend/src/api.js`, `frontend/src/stores/devices.js`, `frontend/src/views/`, `frontend/src/utils/sse.js` | Polling size/frequency, late responses, streaming completion and per-device results |
| Fleet Help and retrieval | `backend/routers/chat.py`, `backend/services/chat_prompt.py`, `backend/services/job_context.py`, `backend/services/context_manager.py`, `backend/services/docs_indexer.py`, `backend/services/job_log_indexer.py` | Shared prompt, fresh SQL evidence, redaction, optional retrieval, bounded work and provider failures |
| NAT and ingestion | `nat/config.yml`, `nat/ingest.py`, `nat/embedding_response.py`, `tools/dgx-doc-ingester/src/main.rs` | Cross-language embedding contracts, image packaging and index rebuild behavior |
| Delivery and SSH | `docker-compose.yml`, `Dockerfile`, `nat/Dockerfile`, `ssh-agent-proxy/`, `scripts/start.sh`, `scripts/enroll_hosts.py` | Dedicated agent, strict host trust, secrets, volumes and running-image drift |

The current service has seven maintenance actions plus device scanning and bulk
user management. Service operations treat devices as standalone; legacy CLI
Kubernetes workflows still exist. Confirm the current catalog in
`backend/routers/operations.py` rather than reviving requirements from old reviews.
Scan freshness, automatic recovery checks, and package approval have distinct
contracts. Read their implementations before changing a shared gate.

SQL activity and full job logs are authoritative; Milvus is derived retrieval.
`/api/v2/jobs/{job_id}/progress` deliberately avoids full logs and artifacts.
The web startup lifecycle acquires an executor lease, reconciles interrupted
work, and starts background job-index reconciliation. Importing or starting the
real app against live configuration is not a read-only test.

The canonical Fleet Help prompt is `workflow.system_prompt` in `nat/config.yml`.
NAT loads prepared configuration at startup; the direct fallback reads this
mounted source on each request. Keep its catalog and `docs/fleet-manager-ui.md`
aligned with routes and capability gates. `job_log_indexer._sanitize_text` also
filters fresh `job_context` evidence. Fixing it affects new context and newly
indexed documents; it does not rewrite existing vectors or raw job logs.

## Docker and evidence

Discover actual services each time. The current Compose services are:

| Service | Relevant evidence |
| --- | --- |
| `web` | FastAPI, executor lifecycle, SSH/Ansible launch errors, index reconciliation |
| `nat` | NAT startup/configuration, provider calls, retrieval and streaming errors; no Compose healthcheck currently |
| `ssh-agent-proxy` | Socket readiness and proxy failures; a socket healthcheck does not prove the key is unlocked |
| `milvus` | Search/index failures, memory and storage errors |
| `etcd` | Metadata availability, slow requests and storage warnings |

The web image contains Python/backend code, the frontend build, and the Rust
ingester. Playbooks, scripts, docs and NAT configuration are mounted. Local code
and an old image can disagree; a mounted edit can already affect running jobs.
Keep image IDs/start times with runtime evidence and avoid assuming HEAD is
deployed. `/api/health` is a shallow application probe.

The web data directory defaults to `/app/data`: `logs/<job_id>.log`, scan/report
artifacts, SQLite state, and strict SSH known hosts live there. Never export the
whole volume or database merely to collect a few failure excerpts. Configuration
can override these defaults. See the evidence guide for scoped log access.

## Validation map

Read `Makefile`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`,
`requirements-dev.txt`, `ruff.toml`, and `frontend/package.json` before choosing
gates. The baseline is Python 3.12, Node 22, and Rust 1.85 or newer.

| Scope | Current check |
| --- | --- |
| Python/Ansible behavior | `bash scripts/check-backend.sh` (accepts pytest paths/options; requires Ansible so integration cases cannot silently disappear) |
| Frontend behavior/build | `npm --prefix frontend test` and `npm --prefix frontend run build` |
| Rust ingestion | `cargo test --locked --manifest-path tools/dgx-doc-ingester/Cargo.toml`; CI also tests Rust 1.85.0 |
| Local aggregate | `make check` runs all-file hooks, backend, frontend tests/build and Rust tests |
| Changed-file hygiene | `.venv/bin/pre-commit run --files <changed-files>`; include new untracked files explicitly |
| Push parity | `pre-commit run --all-files --hook-stage pre-push` |
| Ansible syntax/lint | `ansible-playbook -i localhost, <playbook> --syntax-check`; `ansible-lint --profile min playbooks`; isolated `tests/ansible/dgx_detection.yml` fixture |
| Configuration | `docker compose config --quiet`; never print resolved configuration or start services for a syntax check |
| CI-only additions | Python compilation, Python/npm/Cargo dependency audits, and the Rust minimum-version check |
| Skill collector | `python3 -m unittest discover -s .agents/skills/server-maintenance-review-and-remediate/scripts -p 'test_*.py'` |

Backend tests live in `tests/`; frontend uses Node's built-in test runner,
including mounted Vue fixtures under `frontend/test-support/`. Inspect mocks and
discovery rather than assuming browser coverage. Rust tests are in the ingester.
Do not install hooks just to execute them. Do not use `make` without a target:
the default is `start`, which starts the live stack and can enroll hosts.

Historical leads: `docs/reviews/operations-review.md`,
`docs/reviews/reliability-implementation.md`, `docs/codebase-review.txt`, and
`docs/reviews/code-review-followup.txt`. Reconcile their dates and claims against
current source; keep reusable current guidance in the owning guide.
