# Fleet Manager implementation QA

final result: passed

Reviewed September 25, 2026 in native Chrome against the actual Vue implementation with isolated synthetic API fixtures. This result covers the frontend implementation and the checks below, not real-machine execution or a formal accessibility certification.

## Reference and comparison

- Reference: [light proposal](design-review/screenshots/21-proposal-light.jpg), [dark proposal](design-review/screenshots/22-proposal-dark.jpg), [lower-page proposal](design-review/screenshots/23-proposal-lower.jpg).
- Implementation: [light Overview](design-review/implementation/02-overview-light-revised.jpg), [dark Overview](design-review/implementation/06-overview-dark.jpg), [lower page](design-review/implementation/07-overview-dark-lower.jpg).
- Both sets were captured at 3024 × 1898 physical pixels, approximately 1512 × 949 CSS px including Chrome's toolbar at 2× density. Each desktop reference and implementation pair was opened together for comparison. Lower-page captures were also compared together for content and hierarchy; they have different scroll positions.
- Full-view comparison: the condition brief leads; recovery leads the wider triage column; active work and outcomes occupy the right column; observation coverage and composition remain secondary. The implementation uses the product's full content width because the proposal's review toolbar and annotation column are not product content.
- Focused comparison: inspected heading hierarchy, recovery row, active-job density, outcome counts, evidence disclosures, bottom coverage panels, exact-target Operations handoff, and typed confirmation. Product copy and real-data fallbacks replace schematic examples. Unsupported trajectory/history annotations are intentionally omitted.
- Typography: explicit system UI stack, monospace identities/logs, 28px Overview title, 22px condition heading, 18px panel headings. No dependency on an unloaded Inter font.
- Layout: 1.65:1 desktop columns, bounded readable container, single-column triage below 900px, stacked support panels below 620px. Evidence lists and target lists have bounded scrolling without truncating the available records.
- Color: retained the existing neutral light/black-gray dark identity. Added independent link, focus, control-border and warning/danger text tokens. The proposal's blue-black surfaces were schematic; adopting them globally was unnecessary.
- Assets: existing Font Awesome icon vocabulary and CSS surfaces; no replacement brand imagery or new component library.

## Findings fixed during QA

| Severity | Finding | Fix and evidence |
| --- | --- | --- |
| P2 | Active rows pushed outcome counts below the initial desktop viewport. | Put status and operation on one line and tightened row spacing. Counts are visible in [revised light](design-review/implementation/02-overview-light-revised.jpg) and dark captures. |
| P2 | Sticky navigation consumed too much of a short viewport at 400% zoom. | Navigation scrolls normally below 500px viewport height. [Revised 400% triage](design-review/implementation/19-overview-400-revised.jpg) shows full-width content without the persistent header obstruction. |
| P2 | Attention group heading skipped from h2 to h4. | Changed group titles to h3; confirmed the native accessibility tree. |
| P2 | Polling identical devices could announce new observations while inspecting the queue. | Ignore equivalent device snapshots; retain focus and the open disclosure during unchanged refreshes. |
| P3 | Singular exclusions read “1 unavailable devices.” | Corrected singular device/target wording. |

The earlier browser-capture block was resolved when the user unlocked the Mac and opened Chrome. Native browser checks resumed; Playwright was not used.

## Interaction checks

- Skip link activates with Enter, retains the `#/` route, and focuses main content. The next Tab reaches Refresh view.
- Native evidence disclosures expose all overlapping conditions, observation timestamps, and recovery details. The large fixture exposes all 199 storage cases; searching `node-199` returns the final device, not merely the initially summarized names.
- Jobs opens with named targets, closes with Escape, and returns focus to its trigger. Manage also closes with Escape from a child link and returns focus to its summary. Focus rings remain visible in both themes.
- Recovery → Operations selects only `worker-02`, shows the specific operation and its eligibility, and allows clearing all selection without expanding scope. [Handoff](design-review/implementation/03-recovery-handoff.jpg).
- Reboot review receives `atlas-01` and `gpu-02`, explains why stale `atlas-01` is excluded, and includes only `gpu-02` in confirmation. Incorrect typed text leaves confirmation disabled; the exact name enables it. Escape cancels and returns focus to Run. [Confirmation](design-review/implementation/04-typed-confirmation.jpg). No operation executed.
- Offline group → Devices shows three rows and both offline/stale conditions. Device detail → Devices retains the reason filter and table presentation. [Filtered inventory](design-review/implementation/05-offline-devices.jpg).
- Activity adverse filter shows failed and recovery-required jobs. Expanding a recovery job preserves the filter in the URL and displays logs; its Operations link resolves the historical inventory name to the exact current device.
- Refreshed mixed-fleet Chrome console: no errors or warnings at default log levels and no reported Issues. [Console](design-review/implementation/20-console.jpg).

## State and responsive coverage

| State | Evidence and result |
| --- | --- |
| Empty | [First run](design-review/implementation/08-empty.jpg): three enrollment/review steps plus Add and CSV entry points. |
| One unscanned device | [One device](design-review/implementation/13-state-one.jpg): unknown status and missing storage stay unknown; scanning is the first next step. |
| Five devices | [Small fleet](design-review/implementation/13-state-five.jpg): no recovery case, so connectivity becomes the priority. |
| Offline-only | [Offline](design-review/implementation/13-state-offline.jpg): explicit “No devices currently reported reachable,” with no invented outage duration. |
| 200 affected devices | [Large fleet](design-review/implementation/11-large-fleet.jpg): recovery on node-200 outranks 199 storage cases. [Search](design-review/implementation/12-large-search.jpg) plus accessibility-tree inspection verifies full evidence access. |
| API unavailable | [Unavailable](design-review/implementation/09-unavailable.jpg): unknown device count and Retry, not onboarding or a healthy assessment. |
| Jobs unavailable | [Partial failure](design-review/implementation/10-partial-failure.jpg): successful device observations remain; active work and outcome sections explicitly report unknown state. |
| No current device alerts | [Healthy fixture](design-review/implementation/13-state-healthy.jpg): qualifies the assessment as the latest recorded facts. |
| Automatic dark theme | [No explicit theme](design-review/implementation/18-automatic-theme.jpg): honors the Mac's dark preference. Explicit light overrides it; explicit dark also verified. |
| 200% zoom | [200%](design-review/implementation/14-overview-200.jpg): columns reflow, controls remain labeled and usable. |
| 400% zoom | Approximately 378 CSS px wide. [Overview](design-review/implementation/19-overview-400-revised.jpg), [Jobs dropdown](design-review/implementation/17-jobs-400.jpg), and [Operations](design-review/implementation/21-operations-400.jpg) retain readable wrapping and contained controls. Navigation's short-height refinement is reflected in the revised Overview and Operations captures. |

Token contrast calculations: link text 6.16:1 light / 9.75:1 dark; muted text on page 5.20:1 / 5.01:1; control border against field surface 4.15:1 / 5.17:1; danger text on its composited status surface 5.56:1 / 8.15:1; warning text 5.71:1 / 8.67:1. Status always includes text. Reduced-motion behavior was inspected in the global CSS override; the system motion preference was not changed.

## Automated validation and limits

- `npm test`: 20 passed. Covers recovery-first ranking, overlapping reasons, unknown disk readings, exact inventory matching, scope parsing, completed-outcome denominators, independently failing API resources, retained observations, concurrent refreshes, and actual Vue rendering of unavailable/empty/large/partial-error states.
- `npm run build`: passed (96 modules).
- `git diff --check`: passed. All modified and added artifacts are inside `frontend/`.
- No backend changes, real-machine actions, deployment, or component-library dependency. Preview mutation requests return 409.
- Screen-reader speech, touch hardware, changing-device polling behavior, and production API integration were not end-to-end tested. The accessibility tree, keyboard paths, CSS, retained-observation tests, and synthetic runtime checks provide the recorded evidence.
- Historical trends, outage starts, stable job/device identity across renames, and complete time-window aggregates remain backend requirements in [the review](design-review/REVIEW.md). No unavailable metric is fabricated.
