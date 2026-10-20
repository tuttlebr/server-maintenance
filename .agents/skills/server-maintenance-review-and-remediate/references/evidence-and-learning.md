# Evidence collection and learning

## Collection

Run `scripts/collect_evidence.py` from this skill against the checkout. It uses
only the Python standard library, Git, and Docker CLI. It performs Git reads,
Compose service/container discovery, selected container inspection, and log
reads. It does not start services, execute fleet jobs, export `.env` contents, or
update review baselines. Compose itself uses the existing environment normally.

Default output: a unique directory under ignored `data/skill-reviews/`, mode
0700, containing `evidence.json` mode 0600. Each command records its outcome.
Logs are limited to 500 lines per container, 1 MiB per command, and 20 seconds
per command. Increase limits only for a specific diagnostic gap:

```bash
python3 .agents/skills/server-maintenance-review-and-remediate/scripts/collect_evidence.py \
  --repo . --service web --service nat --since 4h --tail 1000
```

The normal window starts five minutes before that service's last reviewed
sample, capped to the most recent 24 hours. The end is fixed at collection start.
`--since` explicitly overrides the start. Capped windows, tail limits, output
limits, container replacement, log rotation, and failures leave gaps. Inspect
the metadata and never call a bounded sample a complete log history.

Redaction removes common credential assignments, auth headers, URL credentials,
key blocks, and token shapes. It is best effort, not proof of anonymization.
Evidence can still contain hostnames, addresses, user text, or unusual secrets.
Keep it local and ignored; manually minimize any excerpts before putting them in
tracked docs or sending them to an external service. Use aliases for devices.
Do not retain raw logs in the skill's memory.

Docker unavailable, missing `.env`, stopped services, no log records, and a
successful healthy observation are different outcomes. The collector records
them without trying to fix the runtime. Continue source/test/doc review and
retain the unobserved service's previous cursor. If extra Compose files or a
project name are used, set the standard Compose environment explicitly; verify
the recorded project and service labels match the intended stack.

## Focused investigation

Correlate service timestamps with container start time, a concrete request/job,
the changed code path, and tests. For suspected job failures, container stdout
may omit the Ansible details. Read the relevant job's existing log through its
authenticated detail API, or use a read-only `docker compose exec -T web` command
to tail only `/app/data/logs/<verified-job-id>.log`. Validate the identifier and
configured data directory first, avoid shell interpolation of log-derived text,
and apply the same local-output/redaction restrictions. Do not start a scan,
replay a job, enumerate stored credentials, or copy the fleet database to obtain
evidence. No provider call or paid reindex is required for collection.

Capture additional windows before deciding a repeated warning is a defect.
Confirm whether each symptom is current, historical, expected, transient,
externally caused, or still unknown. A disappeared error after container
replacement does not establish a fix.

## State and memory

`references/review-state.json` is compact, tracked memory, not a log archive:

- `repository_reviewed_through`: Git commit whose pending changes have actually
  been reviewed. Advance only after the entire prior-baseline-to-starting-HEAD
  range is accounted for. A narrow review cannot skip the rest of the range.
  It is a review cursor, not a claim every finding was fixed.
- `baseline_scope`: preserve the initial comparison base, first reviewed HEAD,
  and scope exclusions when establishing a cursor without a prior review. This
  provenance prevents subsequent incremental runs from implying a full audit.
- `docker_samples_reviewed_through`: service to UTC collection end time. Advance
  a service only when its successful sample was actually inspected. Missing,
  failed, timed-out or byte-truncated reads retain the previous cursor. A
  tail-capped or time-capped sample may advance only with its gap recorded in
  `pending_work`; this cursor explicitly tracks samples, not complete coverage.
- `last_run`: replace on every invocation with UTC time, starting HEAD, scope,
  complete/partial/blocked status, dirty-worktree coverage, checks and outcomes,
  doc changes or verified no-change reason, learning changes or no-change
  reason, and a local evidence path. Never store raw excerpts or private values.
- `pending_work`: carry unresolved findings, skipped scope, and evidence gaps
  forward with stable IDs, evidence pointers, and a concrete next check. Close
  only with evidence; remove resolved items after any reusable lesson is saved.

Collection cannot advance these fields. Write the state after reviewing evidence
and validation, using a temporary file plus atomic rename. If interrupted before
that point, the old cursors remain valid. Do not invent a completed baseline for
skill creation, read-only collection, or a test run. When a state schema changes,
migrate existing fields deliberately rather than silently discarding memory.

Use `references/lessons.md` for reusable causal knowledge. Each lesson needs:
condition, observed failure mechanism, future check/action, source or regression
evidence, verification level, and invalidation condition. A hypothesis belongs
in pending work until confirmed. Evidence from code/tests can establish a
contract without claiming it was reproduced on live devices.

Merge duplicates, revise changed facts, and remove obsolete advice. Keep only
high-signal lessons that alter future review behavior; do not grow a per-run
diary. Update current user/operator documentation in its owning file, repository
facts in the repository guide, and review procedure in `SKILL.md`.

Validate edited Python helpers with their unittest suite and the repository
lint/hygiene gates. When available, run the installed skill-creator
`scripts/quick_validate.py` against the skill directory. Otherwise check YAML
frontmatter, relative links, metadata, and absence of unfinished scaffolds
directly, and report which validator was unavailable.
