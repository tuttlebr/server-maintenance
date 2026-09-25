# Fleet Manager: make the next decision obvious

Design Engineering review · 25 September 2026 · Source snapshot `e4155a7`

**Replace the reachability hero, count-card row, and chronological feed with a ranked operational work queue.** Overview should tell an operator what matters, how current the evidence is, what is already being handled, and the next safe step. It currently makes the operator assemble that answer across several screens.

[Open the annotated proposal](proposal.html?theme=light) · [Current mixed-fleet preview](/?theme=light#/) · [Recommendation priorities](#priorities)

This is a design review and a separate review artifact. Application source and backend behavior are unchanged. All device names, endpoints, jobs, and outcomes shown here are synthetic.

## The ten-second contract

| Operator question | Answer the redesigned Overview must give | Today’s gap |
|---|---|---|
| Can I trust this picture? | API refresh state, observation coverage, stale or missing facts | A failed initial load looks like an empty fleet. No observation time appears. |
| What needs me first? | Highest-consequence condition, affected devices, next safe step | Alphabetical device order determines the first seven alerts. |
| Is someone or something already handling it? | Running/queued jobs, target overlap, current phase | Count plus a chronological feed; work can be pushed out by newer jobs. |
| What recently went wrong? | Adverse job outcomes with device scope and a link to evidence | Six newest jobs can all look benign while recovery is needed. |
| Is the situation improving? | New/resolved conditions over a defined, comparable period | No device-state history is exposed. An honest “not measured” beats a fabricated trend. |
| What can I safely do next? | Review a specific investigation or operation with explicit scope | Device links preserve identity, but often lose the reason and intended action. |

Composition and utilization are secondary questions. They earn space when they change a decision. A count of GPUs should not outrank a machine left in an uncertain recovery state.

## Evidence and scope

I ran the existing Vue screens in a local Vite harness with mocked API responses, then followed Overview → attention-filtered Devices → device detail → Operations → Activity → recovery evidence, visited Access and Context, and returned to Overview. I captured explicit light/dark themes, empty/one/five-device states, an offline-only fleet, 200 alerting devices, a failed initial load, and keyboard/zoom behavior.

The suggested port, `localhost:8080`, is occupied by Docker Model Runner. The review therefore runs at `127.0.0.1:9012`, with no production proxy and all operation requests blocked. `make start` was not run because it would recreate infrastructure and synchronize real enrollment data. The harness renders existing components; it does not emulate Ansible or validate backend eligibility. Operations fixtures are intentionally small.

Screenshots are original captures from this run, inspected after saving. Desktop captures are 3024 × 1898 pixels at native scale, approximately a 1512 CSS-pixel-wide browser. Exact image sizes are recorded by the files. Screenshot 20 uses 200% browser zoom. This is not a full screen-reader, mobile-device, or WCAG conformance audit. Automatic OS dark-mode switching was inspected in source; rendered dark-theme evidence uses `data-theme="dark"`.

## Current experience: findings in journey order

### 1. Overview spends its strongest hierarchy on the least actionable fact

![01. Current mixed-fleet Overview at initial scroll position](screenshots/01-overview-mixed-light.jpg)

**Strength:** the neutral identity, stable top navigation, familiar link styling, explicit status words, and modest visual vocabulary fit an operator tool. The components look related. Keep that foundation.

**Finding F1, high:** the broad hero, large headline, health bar, and five equal cards make reachability and inventory dominate. In this fixture, “3 devices offline” gets the largest treatment; interrupted maintenance on `worker-02` gets no visible treatment. The first useful action is below a large amount of repeated counting. Two primary header buttons compete without reference to the current problem.

**Recommendation:** remove the hero and all five metric cards. Use a compact condition brief and one dominant triage area. Keep “12 devices” as context. Put Add device in a secondary position after enrollment. Present Refresh as “Refresh view”; reserve “Review scan targets” for gathering new device evidence. Those are different tasks.

**Pushback on the brief:** the answer is not to add a sparkline to each existing card. Inventory growth is rarely an operational priority. Arbitrary deltas would add visual noise before the product has reliable time-window semantics.

### 2. “Priorities” is not actually prioritized

![02. Full current attention and activity lists](screenshots/02-overview-mixed-lists.jpg)

**Finding F2, critical:** the seven attention rows cover only three of seven affected devices. `atlas-01` consumes three rows; stale facts precede the offline condition on `atlas-02`. The recovery-required device is missing entirely. Nothing says “showing 7 of 12 conditions.” The count and list use different units: unique devices versus individual reasons.

**Recommendation:** group by the next safe step and rank by consequence. Keep a deduplicated fleet count, label group overlap, show affected names, and expose all reasons within the group. Recovery must stay visible regardless of device name. The 200-device test makes this more obvious: 199 storage warnings crowd out recovery on `node-200` [screenshot 15](screenshots/15-overview-200-alerts.jpg).

Hardcoded rules are not inherently a design failure. Transparent, deterministic rules are a good starting point. The failure is their presentation as an unranked, silently truncated list. Configurable policy, durable ownership, and alert suppression can follow later.

### 3. The handoff preserves the device but loses the problem

![03. Attention-filtered Devices](screenshots/03-devices-attention.jpg)

**Strength:** the Overview link correctly selects “Needs attention” and returns seven devices.

**Finding F3, high:** hardware cards replace the reason-based queue. A device can appear Online in this filtered set without explaining that it needs recovery verification or has stale facts. Operators have to rediscover why they arrived. Capabilities are summarized as a number rather than the operation they enable.

**Recommendation:** when arriving from a triage group, default Devices to a compact table with device, condition, evidence age, relevant capability, and next step. Display an explicit filter chip such as “Recovery required”; retain it through detail and Back. Keep cards as an optional inventory view. The current filter deep link is useful, but its explanation must survive navigation.

![04. Offline-device detail](screenshots/04-device-offline.jpg)

**Strength:** device detail already separates last seen, last discovery, and maintenance mode, and warns about stale facts. Pull that distinction up into Overview. “Last seen” is not an outage start time.

**Quick hit:** “Operations” in the header and an “Operations” subtab promise similar destinations. The subtab lists capability IDs, while the header opens the action catalog. Rename the subtab “Capabilities” or merge its content into a relevant device summary. Recovery links should select the recovery operation, not merely open the catalog.

### 4. Operations exposes scope, but distributes it across the catalog

![05. Device-to-Operations handoff](screenshots/05-operations-handoff.jpg)

**Strength:** impact labels, eligible targets, unavailable-target disclosures, and existing typed confirmations are the right raw materials.

**Finding F4, medium:** a sidebar saying “1 selected” does not identify the device; targets repeat in each operation card. A selection is shared across the catalog even though the user perceives local checkboxes. “Select eligible” also lacks a specific operation in its wording.

**Recommendation:** an Overview handoff should land on one operation with an explicit device scope and eligibility review. Show selected names, supported/excluded counts, reasons, prerequisites, and the expected impact before continuing to the existing confirmation. Keep the catalog for browsing. Do not add one-click reboot, update, cleanup, or “Fix fleet” controls to Overview.

The screenshot uses a reduced fixture catalog. It supports a critique of layout and scope presentation, not a conclusion about production eligibility rules.

### 5. Recent activity hides the outcomes that matter

![06. Full Activity list exposes outcomes absent from Overview](screenshots/06-activity-outcomes.jpg)

**Finding F5, high:** the Overview’s six recent rows show two active jobs and four successes. Activity exposes a recovery-required update and two failures immediately below them. Routine scans can push adverse outcomes out of the landing page.

**Recommendation:** dedicate space to Work in progress, then summarize recent completed outcomes and highlight adverse results separately. Distinguish a historical failed job from an unresolved current device condition; the former does not prove the latter.

![07. Recovery job detail and evidence](screenshots/07-activity-recovery-detail.jpg)

**Strength:** per-device outcomes, error summaries, structured results, and logs already exist in the detailed experience. Keep raw logs one layer down. Overview should offer a concise statement with a specific evidence link.

**Quick hits:** persist Activity’s status/operation/device/time filters in the URL. The existing `job` deep link is useful; the Overview “Active jobs” metric currently opens unfiltered Activity. Recovery guidance links to generic Operations and loses the affected-device scope. Fix that handoff before adding more analytics.

### 6. Access and Context deserve different navigation weight

| Screen | Keep | Quick-hit finding and direction |
|---|---|---|
| [08. Access](screenshots/08-access.jpg) | Explicit target scope, stale/recovery labels, inspect-before-change guidance | Rename to “Device access” to distinguish machine accounts from application access. Show selected names persistently. Keep scope and typed confirmation. |
| [09. Context](screenshots/09-context.jpg) | Device-document association and explicit indexing state | “Context” is implementation language. Rename to “Knowledge sources” and place it under Fleet Help or a secondary management area, with direct links from device documentation. Index-record counts do not deserve equal navigation weight with fleet operations. |

**The intentional overreach:** make Overview the home for operational follow-through, absorbing prioritization from Devices and active/recovery work from Activity. Reduce the primary navigation to Overview, Devices, Operations, and Activity. Keep Device access easy to reach in secondary navigation; move Knowledge sources beside Fleet Help. The tradeoff is one extra step for less frequent administrative work. Validate that tradeoff with operators who provision accounts daily. Preserve existing URLs and direct links.

Do not merge the full job archive or execution forms into Overview. It should organize decisions and handoffs, while Operations owns execution and Activity owns evidence.

## State coverage and accessibility

| Evidence | Observed behavior | Proposed behavior |
|---|---|---|
| [10. Dark theme](screenshots/10-overview-dark.jpg) | Theme surfaces work, but small blue links are subdued | Separate link-text colors from filled-button colors; validate both theme palettes. |
| [11. Empty](screenshots/11-overview-empty.jpg) | Zero cards, a zero health bar, “No current device alerts,” and an enabled Scan fleet | Replace the dashboard with Add/import → verify identity → inspect first facts. No health assessment until a device has evidence. |
| [12. One device](screenshots/12-overview-one.jpg) | Full dashboard for one unscanned device; “1 device need a scan” | Name the device and its next discovery step. Show onboarding progress, not fleet percentages. |
| [13. Five devices](screenshots/13-overview-five.jpg) | Same count-heavy structure | Show all affected device names; expand small groups without forcing detail clicks. Avoid trend charts with tiny samples. |
| [14. Offline-only](screenshots/14-overview-offline.jpg) | Red reachability bar, repeated stale/offline/storage rows | Lead with “No devices currently reported reachable.” Group the connectivity investigation; keep last-known evidence visible and qualified. Do not assert a shared network outage. |
| [15. 200 alerts](screenshots/15-overview-200-alerts.jpg) | “All devices are reachable” over 200 attention devices; first seven storage rows | Put recovery first, then a 199-device storage group with affected scope, search, and progressive disclosure. |
| [16. Initial API error](screenshots/16-overview-load-error.jpg) | Looks like first run and claims no device alerts; active count alone is unknown | “Fleet state unavailable,” Retry, no zero counts or all-clear claims. On later failures retain observations with a conspicuous age/error label. |
| [17. All reachable with warnings](screenshots/17-overview-reachable-with-recovery.jpg) | Reassuring headline despite recovery/stale/reboot/storage conditions | Treat reachability as one dimension. Condition brief leads with the most consequential known issue. |
| [18. Focused skip link](screenshots/18-keyboard-skip-focus.jpg), [19. activation](screenshots/19-skip-link-broken-route.jpg) | Focus is visible, but Enter navigates to `#/main-content`, producing a blank route | Preserve the skip link and make it focus the main landmark without changing the application route. Verify with keyboard on every main view. |
| [20. 200% zoom](screenshots/20-overview-zoom.jpg) | Header reflows; primary nav becomes icons. Active-jobs control loses its visible contents | Keep an explicit Jobs label/count or accessible menu entry at narrow widths. Priorities must stay ahead of inventory chrome. |

**F6, critical: the skip link is present but broken in the tested hash-router flow.** This is an observed interaction failure, not a theoretical markup concern. A bypass mechanism must actually take the user past repeated navigation. [W3C bypass-block guidance](https://www.w3.org/WAI/WCAG22/Understanding/bypass-blocks.html).

**F7, medium: theme tokens are not yet sufficient for all uses.** Calculated from the declared colors, `#1769d2` on the dark card surface `#111111` is about **3.59:1**. The normal-size “View devices”/“View all” links need **4.5:1**. The same blue on white is about 5.27:1, so simply brightening the shared accent everywhere would compromise white-on-blue buttons. Add separate text, fill, and focus roles. [W3C text-contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).

The dark border token `#3a3a3a` against `#111111` is about 1.66:1. Decorative card borders need not all become high contrast; essential control boundaries and states need their own evaluation and tokens. [W3C non-text contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html).

Preserve real links, status words, visible focus, labeled controls, and existing confirmation safeguards. New group disclosures need buttons, `aria-expanded`, names/counts in accessible labels, logical focus return, and no nested interactive row controls. Announce refresh completion or failure politely; do not repeatedly announce the whole queue or reorder the item under keyboard focus. Use semantic lists/tables, full timestamps alongside relative time, and reduced-motion support. Test screen-reader navigation, modal focus trapping/return, narrow-phone reflow, 400% zoom, forced colors, and OS theme changes before calling the implementation accessible.

## Annotated redesign: component and data inventory

The [proposal](proposal.html?theme=light) includes mixed, 200-alert, first-run, and unavailable states plus light/dark/automatic theme controls. Numbered markers correspond to this inventory. It is a schematic design artifact, not a new implementation of Dashboard.vue. Links demonstrate existing destinations; richer group filters and operation-specific handoffs below remain requirements.

![21. Annotated proposed Overview](screenshots/21-proposal-light.jpg)

[Dark proposal](screenshots/22-proposal-dark.jpg) · [Coverage and secondary panels](screenshots/23-proposal-lower.jpg) · [200-alert proposal](screenshots/24-proposal-200-alerts.jpg) · [First run](screenshots/25-proposal-first-run.jpg) · [Unavailable](screenshots/26-proposal-unavailable.jpg)

| Marker / component | Purpose and interaction | Data and implementation boundary |
|---|---|---|
| **1. Evidence header** | Small title, inventory count, API refresh time, separate device-observation coverage. Retry inline on error. | **Frontend only:** store `loading`, `hasLoadedOnce`, `error`, `lastUpdated`; device `facts_stale`, `discovered_at`, `last_seen`. API response freshness is not device freshness. Track per-resource fetch results so a jobs failure does not erase a successful device observation. |
| **2. Condition brief** | One consequence-led sentence, highest-priority named issue, compact last-known reachability. “Unknown” is explicit. | **Frontend only:** unique device IDs and current attention fields. No health percentage. **Needs backend** for direction of change, duration of offline state, or a durable since-last-visit comparison. |
| **3. Next steps queue** | Group by recovery, connectivity, storage investigation, verification, planned reboot. Expand affected devices; review the relevant action. Keep recovery visible at any fleet size. | **Frontend only:** current fields, device names/IDs, `recovery_reason`, timestamps; `/operations` for eligibility/exclusion reasons. New route handling for group reason and batch IDs. **Needs backend** for first-seen time, acknowledgment, assignment, snooze, durable resolution, or policy-controlled prioritization. |
| **4. Work in progress** | Running/queued/cancelling jobs, targets, phase, start/queue age, direct output link. Show overlap with a suggested investigation. | **Frontend only:** existing `activeJobs`, summary `active_count`, job `phase`, `started_at`, `created_at`, `target_devices`, `device_results` where populated. Page the active endpoint when count exceeds loaded records. No percent complete or ETA without reliable progress telemetry. |
| **5. Recent outcomes** | Separate success, failure, recovery, cancellation. Highlight recent adverse outcomes; let the operator inspect evidence. | **Frontend only:** bounded jobs sample labeled “latest N completed in loaded sample”; `playbook`, status, timestamps, error summary, per-device outcomes. **Needs backend** for efficient, consistent 24h/7d aggregation by operation and stable target identity. |
| **6. Observation coverage / pressure** | Worst observed root disks, stale/unknown readings, reported denominator. Review inspection before cleanup. | **Frontend only:** `disk_root_percent`, stale state, scan timestamp; optionally latest structured storage artifacts via job detail. Percentages do not reveal free bytes or time-to-full. **Needs backend** for usage history, growth rates, normalized per-mount byte capacity, forecast, and scalable latest-observation retrieval. |
| **7. Composition / readiness entry** | Compact disjoint composition below triage. Expand operation-specific eligible/blocked/unknown scope. | **Frontend only:** `kind`, transport, capabilities; `/operations` eligible IDs and excluded reasons. A GPU capability count is not GPU utilization. Driver/Fabric Manager/MIG/Kubernetes labels stay inside integration-specific details. **Needs backend** for uniform readiness policy, historical readiness, and normalized capacity/utilization coverage. |
| **8. Change digest, later** | “New / resolved / still active” conditions plus comparable outcome windows. Include definition, period, sample size, coverage, and links. | **Needs backend:** timestamped condition/observation events, stable IDs, persistence of cleared conditions, user visit watermark, defined comparison windows. Do not derive fleet-health history from job logs alone. |
| **9. First-run replacement** | Connect one device or import CSV; show identity verification, discovered facts, first read-only inspection. | **Frontend only:** successful inventory load, device count, discovery/observation fields, current add/import flow and supported operations. Enrollment success does not imply the first operation succeeded. |

### What “ranked” means

Use explicit consequence bands, not a mysterious score: **recovery verification → offline investigation → storage pressure → missing/stale evidence → planned reboot**. Within a band, prefer more consequential evidence (for example, greater observed disk pressure), then affected-device count, then a stable name/ID tie-break. If timestamps are available, show observation age; do not invent an alert age. These are proposed defaults, not universal SRE policy.

One device may belong to several groups. Show “7 affected devices; groups overlap.” In expanded device rows, show all conditions and a recommended first step. A stale disk observation stays visible, but verification gates the cleanup recommendation. A recovery gate outranks a reboot suggestion. Grouping is organizational, not evidence of a common cause or permission for one bulk operation.

Batch only after reviewing the exact scope, operation compatibility, freshness, exclusions, and current reservations. The frontend can preview this with existing operation data; the backend remains authoritative at execution. Match active-job targets to device `inventory_name` where available and mark unresolved target strings as unknown. A durable job-to-device ID relation is a backend requirement.

### Handoffs are part of the design

| Entry | Landing contract | Boundary |
|---|---|---|
| Recovery group | Affected-device evidence, then Verify recovery with exact targets and prerequisites | **Frontend only** route/state work using existing operations. Recovery completion still requires backend verification. |
| Storage group | Affected disks and observation ages; review Analyze storage eligibility | **Frontend only.** Never map pressure directly to destructive cleanup. |
| Verification group | Stale/never-scanned devices, existing scans, supported scan targets | **Frontend only** for review and existing per-device scans. A single new arbitrary-batch scan endpoint would **need backend** if current operations cannot express it. |
| Running job | Correct job expanded, phase and targets immediately visible, return to Overview | **Frontend only.** |
| Recent failure | Selected job plus per-device outcomes and error evidence | **Frontend only.** A “resolved” state needs a trustworthy relation to later evidence. |

### Time and outcome semantics

The backend already exposes more than the seed brief: device `last_seen`, `discovered_at`, `recovery_reason`, maintenance fields, and arbitrary facts; jobs expose start/finish times, duration, error summary, phase, and per-device outcomes. Structured result artifacts are added by the job-detail endpoint. Use these before requesting new telemetry.

`GET /jobs` supports status, playbook, limit (up to 200), and offset. The Overview currently loads only the latest 10 and renders six. The API summary gives active count only. A bounded frontend sample is straightforward. Complete historical analysis is technically possible by paging existing history, but list payloads include logs, ordering is by creation time, and there is no stable snapshot/time-window aggregate contract. A job created before a window can finish inside it. Do not stop paging at a creation-time cutoff and call that a completed-job window.

For the later aggregate, define the window by **finished_at**. Show succeeded, failed, recovery-required, and cancelled separately. If using a rate, use succeeded / (succeeded + failed + recovery-required), with cancellations and active jobs outside that denominator. Always show `n`, compare like operation classes, and distinguish job rate from per-device success. A successful scan must not dilute failed update operations into a reassuring headline. Small samples get counts rather than a claimed trend or “flaky host” label. Historical target attribution should survive renames and device removal.

Do not promise “one action away from healthy.” A scan may reveal new problems; rebooting may not resolve a recovery requirement. Safer copy is “5 devices need verification” or “2 reboots to review.” Do not claim a shared subnet outage based on matching IP prefixes. Proper network/role grouping needs validated site/subnet/role metadata and event timing; current freeform annotations can support explicitly configured labels, not causal diagnosis.

## Visual system direction

Keep Vue, existing native controls, and hand-rolled components for this redesign. The complexity lies in information meaning, state, and scope; a component library will not solve those. Reuse the existing modal and confirmation work after keyboard validation. The cost is maintaining accessible disclosure, filtering, and table patterns yourselves. Reconsider a headless primitive library only when interaction complexity grows enough to justify dependency, styling, and regression costs.

Use the existing neutral surfaces and blue interaction language with these targeted changes:

- Adopt a practical 4/8/12/16/24/32 spacing scale instead of large 15/30/45 jumps. Use 16–20px section padding; avoid card shadows on every row.
- Keep a roughly 1350–1440px maximum work area. Align navigation and content gutters. Use about two-thirds width for priorities and one-third for active work; stack in that order at narrow widths.
- Set task content around 14px, secondary evidence around 12–13px, section headings around 18px, and the page title around 26–28px. Reserve monospace for identifiers and logs. Inter is declared but not loaded in the checked frontend; either bundle it or deliberately embrace the system fallback.
- Separate `link-text`, `action-fill`, `status-text`, `status-surface`, `control-border`, and `focus-ring` roles. For example, the existing light blue can remain a filled button color while dark links use a lighter blue such as `#6fa8ff` (about 7.84:1 on `#111111`). Validate complete foreground/background pairs, including soft status surfaces.
- Use plain labels alongside severity color. Reserve solid red for an urgent condition, not the badge for ordinary running work. Preserve status names when navigation compresses.

Do not widen the dashboard simply to fit more metrics. More width should expose meaningful device names, evidence, and actions. In a typical desktop viewport, the most serious group and current work must be visible without scrolling. On smaller screens, keep the condition brief and first safe step ahead of composition and administrative actions.

## Priorities

| Priority | Recommendation | Scope | Why this order / acceptance |
|---|---|---|---|
| **P0** | Repair the keyboard skip interaction | **Frontend only** | Confirmed route-breaking failure. Enter focuses main content and preserves the current route on all main screens. |
| **P0** | Distinguish loading, unavailable, stale, and true-empty states | **Frontend only** | Prevents false assurance. A 503 never produces zero devices or “No alerts”; later failures retain labeled observations. |
| **P0** | Rank and group attention; make recovery impossible to truncate away | **Frontend only** | Highest operational consequence. `node-200` recovery appears ahead of 199 storage warnings; all affected devices remain reachable. |
| **P1** | Replace hero/cards with condition brief, Next steps, and active work | **Frontend only** | Changes the first ten seconds. Operator can identify top issue, evidence age, current job, and next safe step before navigating. |
| **P1** | Separate adverse outcomes from recency; label sample coverage | **Frontend only** | Failures survive routine scan traffic. Distinguish historical failures from unresolved current state; expose existing job evidence. |
| **P1** | Preserve reason, target scope, and intended operation across handoffs | **Frontend only** | Makes the new queue useful end to end. Devices explains inclusion; Operations shows exact names/exclusions; Activity retains selected job/filter. |
| **P1** | Fix dark link contrast, narrow-width Jobs visibility, and disclosure/focus behavior | **Frontend only** | Accessibility cannot be deferred to visual polish. Test both themes, keyboard, zoom/reflow, reduced motion, and assistive technology. |
| **P1** | Design first-run, one-device, offline-only, and large-fleet variants | **Frontend only** | These are normal operating states, not exceptions. No zero-health dashboard, no misleading green hero, no seven-row ceiling. |
| **P2** | Add pressure/coverage and operation-specific eligibility summaries | **Frontend only** | Makes existing facts useful without overclaiming utilization. Show reported/stale/missing denominators and backend exclusion reasons. |
| **P2** | Provide compact job summaries and consistent time-window aggregates | **Needs backend** | Enables truthful 24h/7d outcomes without loading full log history. Define finish-time windows, stable snapshot/cursor, per-operation/per-device counts, coverage, and target IDs. |
| **P2** | Add device-state history and durable change events | **Needs backend** | Required for trajectory, first-seen/resolved conditions, outage timing, and since-last-visit claims. Store timestamps and observation provenance, not just latest status. |
| **P2** | Reweight navigation and rename Context / Access | **Frontend only** | Reduces competition from administrative work after the operational hierarchy is fixed. Preserve links; validate frequent-access workflows. |
| **P3** | Add ownership, acknowledgment/snooze, validated fleet grouping, and readiness policies | **Needs backend** | Supports team-scale triage. Requires persistence, auditability, permission rules, expiration, and explicit reopening behavior. |
| **P3** | Add normalized capacity history and forecasts | **Needs backend** | Only after timestamps, coverage, mount identities, and byte measurements exist. Avoid decorative sparklines built from inconsistent samples. |

The first implementation slice should combine the P0 fixes with the new condition brief and ranked queue. Then connect handoffs and active/outcome panels. History should be a separately specified backend capability, rather than a dependency that delays the immediate design improvement.

## Validation and limits

The walkthrough confirms visual hierarchy, actual route behavior, the filter handoff, recovery-job expansion, the failed-load presentation, explicit dark styling, visible keyboard focus, skip-link failure, and 200% navigation behavior. Source inspection grounds the data boundaries and confirms existing confirmation patterns. I did not execute changes on machines, authenticate to the production API, test real enrollment, run a screen reader, or measure backend latency. Read-only fixtures cannot establish production failure frequency, common causes, or the usability of every operation form.

For implementation acceptance, run a short ten-second task test: after showing a mixed or 200-alert fleet, ask the operator to identify the highest-priority device/group, evidence freshness, current work, and next safe step. Then require completion of the corresponding handoff without reselecting scope or reconstructing the reason. Include a stale/error case so “I don’t know yet” is a successful interpretation.

### Reproduce this review

From `frontend/`, run `node design-review/preview.mjs`, then open `http://127.0.0.1:9012/design-review/index.html`. The current UI supports `?scenario=mixed|empty|one|five|offline|large|error|reachable` before the hash route, plus `theme=light|dark`. No production service or credentials are used. Stop the Node process to close the preview.

Source grounding: [Overview](../src/views/Dashboard.vue), [fleet store](../src/stores/devices.js), [API client](../src/api.js), [tokens](../src/styles/variables.css), [navigation](../src/components/NavBar.vue), [application shell](../src/App.vue), [Devices](../src/views/Devices.vue), [Operations](../src/views/Operations.vue), and [Activity](../src/views/JobHistory.vue). Backend schemas and jobs routes were read only to verify API capabilities; all review files live under `frontend/design-review/`.

## Screenshot appendix

Select an image to inspect its original capture. All scenarios use synthetic data.

<details>
<summary>Open state, accessibility, and proposal evidence</summary>
<div class="gallery">
<figure><a href="screenshots/08-access.jpg"><img loading="lazy" src="screenshots/08-access.jpg" alt="08. Access"></a><figcaption>08. Access</figcaption></figure>
<figure><a href="screenshots/09-context.jpg"><img loading="lazy" src="screenshots/09-context.jpg" alt="09. Context"></a><figcaption>09. Context</figcaption></figure>
<figure><a href="screenshots/10-overview-dark.jpg"><img loading="lazy" src="screenshots/10-overview-dark.jpg" alt="10. Current dark theme"></a><figcaption>10. Current dark theme</figcaption></figure>
<figure><a href="screenshots/11-overview-empty.jpg"><img loading="lazy" src="screenshots/11-overview-empty.jpg" alt="11. Empty inventory"></a><figcaption>11. Empty inventory</figcaption></figure>
<figure><a href="screenshots/12-overview-one.jpg"><img loading="lazy" src="screenshots/12-overview-one.jpg" alt="12. One unscanned device"></a><figcaption>12. One unscanned device</figcaption></figure>
<figure><a href="screenshots/13-overview-five.jpg"><img loading="lazy" src="screenshots/13-overview-five.jpg" alt="13. Five devices"></a><figcaption>13. Five devices</figcaption></figure>
<figure><a href="screenshots/14-overview-offline.jpg"><img loading="lazy" src="screenshots/14-overview-offline.jpg" alt="14. Offline-only fleet"></a><figcaption>14. Offline-only fleet</figcaption></figure>
<figure><a href="screenshots/15-overview-200-alerts.jpg"><img loading="lazy" src="screenshots/15-overview-200-alerts.jpg" alt="15. 200 alerting devices"></a><figcaption>15. 200 alerting devices</figcaption></figure>
<figure><a href="screenshots/16-overview-load-error.jpg"><img loading="lazy" src="screenshots/16-overview-load-error.jpg" alt="16. Initial API failure"></a><figcaption>16. Initial API failure</figcaption></figure>
<figure><a href="screenshots/17-overview-reachable-with-recovery.jpg"><img loading="lazy" src="screenshots/17-overview-reachable-with-recovery.jpg" alt="17. Reachable with warnings"></a><figcaption>17. Reachable with warnings</figcaption></figure>
<figure><a href="screenshots/18-keyboard-skip-focus.jpg"><img loading="lazy" src="screenshots/18-keyboard-skip-focus.jpg" alt="18. Keyboard skip focus"></a><figcaption>18. Keyboard skip focus</figcaption></figure>
<figure><a href="screenshots/19-skip-link-broken-route.jpg"><img loading="lazy" src="screenshots/19-skip-link-broken-route.jpg" alt="19. Broken skip destination"></a><figcaption>19. Broken skip destination</figcaption></figure>
<figure><a href="screenshots/20-overview-zoom.jpg"><img loading="lazy" src="screenshots/20-overview-zoom.jpg" alt="20. 200% zoom"></a><figcaption>20. 200% zoom</figcaption></figure>
<figure><a href="screenshots/22-proposal-dark.jpg"><img loading="lazy" src="screenshots/22-proposal-dark.jpg" alt="22. Proposed dark theme"></a><figcaption>22. Proposed dark theme</figcaption></figure>
<figure><a href="screenshots/23-proposal-lower.jpg"><img loading="lazy" src="screenshots/23-proposal-lower.jpg" alt="23. Proposed secondary panels"></a><figcaption>23. Proposed secondary panels</figcaption></figure>
<figure><a href="screenshots/24-proposal-200-alerts.jpg"><img loading="lazy" src="screenshots/24-proposal-200-alerts.jpg" alt="24. Proposed 200-alert queue"></a><figcaption>24. Proposed 200-alert queue</figcaption></figure>
<figure><a href="screenshots/25-proposal-first-run.jpg"><img loading="lazy" src="screenshots/25-proposal-first-run.jpg" alt="25. Proposed first run"></a><figcaption>25. Proposed first run</figcaption></figure>
<figure><a href="screenshots/26-proposal-unavailable.jpg"><img loading="lazy" src="screenshots/26-proposal-unavailable.jpg" alt="26. Proposed unavailable state"></a><figcaption>26. Proposed unavailable state</figcaption></figure>
</div>
</details>
