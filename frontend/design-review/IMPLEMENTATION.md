# Overview implementation

The production Vue views now implement the reviewed frontend direction. Backend contracts and execution services are unchanged.

- Compact condition brief and ranked, overlapping attention groups replace the hero and count cards. Recovery outranks storage regardless of name or fleet size. Each group provides a full searchable evidence disclosure, related active jobs, and an explicit target handoff.
- Separate active work, recent completed-job counts, and latest adverse outcomes. Samples are labeled; no fleet trend, outage duration, or time-window success rate is inferred.
- Device, current-job, recent-job, and adverse-job refreshes retain independent observations and error states. First load, true empty, unavailable, and stale observations are distinct. Shared requests coalesce, including explicit refreshes.
- Devices preserves URL filters and reasons, defaults triage to a table, explains inclusion, and retains filters through detail. Cards also show attention reasons.
- Operations accepts a specific operation plus exact device IDs or historical inventory names, keeps the requested scope, identifies selected names/exclusions, and prevents unresolved names from silently expanding scope. Medium/high-impact actions require typed target confirmation. Execution remains in the existing operation API.
- Activity supports URL-bound status, operation, device, and created-time filters plus pagination. Device/time filters explicitly apply to loaded pages. Recovery links carry historical target names into an explicit mapping review.
- Primary navigation now contains Overview, Devices, Operations, and Activity. Manage contains Device access, Knowledge sources, and Fleet Help. URLs are preserved.
- Skip navigation focuses main content without mutating the hash route. Dark link/focus/control tokens are independent from button fills. Jobs remains labeled at narrow widths; disclosure menus support Escape and focus return. Reduced motion is honored.

## Validation

Run `npm test` and `npm run build` from `frontend/`. Regression coverage includes 200-device prioritization, overlapping reasons, missing/invalid readings, exact inventory identity matching, scope parsing, outcome denominators, partial refresh failure, retained observations, concurrent refreshes, and actual Vue rendering of empty/error/large-fleet states.

Run `node design-review/preview.mjs` from `frontend/` for the isolated synthetic preview at http://127.0.0.1:9012/. All operation requests are blocked. `?theme=light|dark&scenario=mixed|empty|one|five|offline|large|error|jobs-error|healthy|reachable` selects a fixture before the hash route.

The review proposal is a reference artifact. Its annotations and hypothetical history section are not part of the production UI. Final rendered comparison and interaction evidence are recorded in `frontend/design-qa.md`.

## Still requires backend support

Durable device-condition history and resolution, reliable fleet trajectory, outage start times, consistent time-window outcome aggregates, durable job-to-device identity across renames/removal, assignment/snooze policies, and normalized capacity forecasts remain the backend requirements specified in REVIEW.md.
