# Market Event Radar Handoff

Last reconciled: 2026-09-21 Asia/Taipei

## Canonical role

`futurenowchen/market-event-radar` is the standalone producer for unattended official market-event snapshots. `futurenowchen/investment-dashboard` is the downstream consumer/presentation layer.

## Verified implementation baseline

Verified code commit: `4dec039d06b10e25e878e12adf34a0829a3edff2`

Later bot commits that only refresh `data/latest.json` / history are expected and do not change this implementation baseline.

Current merged implementation includes:

- official-source-first macro feed, snapshot schema v2, rich release metrics, and US high-signal coverage through Phase 4
- provider-neutral `ConsensusObservation` with strict pre-release/PIT eligibility
- deterministic Surprise engine keyed by `event_family + metric_id`
- optional Trading Economics adapter/mapping/canary retained as a paid BYO-credential reference path
- zero-cost MetaTrader 5 canary parser/private CLI and Windows deployment helper
- PR #23 private overlay v1 with strict `survey_consensus` versus `provider_forecast` semantics
- public `data/latest.json` remains official-source-only
- PR #24 / #25 release-result resilience for FOMC and Census Retail Sales Actual values
- PR #26 official Previous-value completion for FOMC and Retail Sales
- PR #27 first-party Taiwan CBC decision-result resilience with live Actual/Previous verification
- PR #28 first-party Taiwan CBC historical release backfill utility/workflow
- official result retry / producer lookback aligned to the same 48-hour horizon used by snapshot retention and watchdog validation

## 2026-09-17 result-collector incident and recovery

The dashboard-open trigger and GitHub Actions scheduler were not the root cause. A dashboard-open `workflow_dispatch` successfully ran the refresh gate and correctly detected a released FOMC event with missing Actual, but the collector returned `No provider values changed`. The scheduled watchdog also correctly failed on two overdue official results: 2026-09-16 Retail Sales and the 2026-09-16 FOMC decision.

Root causes fixed by PR #24 / #25:

1. FOMC calendar parsing could mistake `Minutes Released ...` dates for policy meetings.
2. Fed target-range parsing did not support mixed-fraction statement text such as `3-3/4 to 4 percent`.
3. Census `retail/sales.html` can lag the current release while the first-party Census Economic Indicators widget is already current.
4. Missing-result retries stopped after 12 hours while snapshots/watchdog retain releases for 48 hours.

PR #24 merge: `402c69f167f18373f0ec4cd9dce0d0f1ecd3259c`.
PR #25 merge: `d7f2307a9d56aa88c8acf4e713e3ec46df7c09ce`.

## Previous-value completeness

After Actual recovery, the production snapshot still exposed a second-layer completeness gap: Retail Sales and FOMC had valid Actual values but blank `previous` fields.

PR #26 (`fb1bb303761a32c47db703bd1943903f998c3e89`) added `v2_event_official_previous_resilience.py` and fixes Previous without hard-coding production values:

- FOMC Previous is read from the immediately preceding official FOMC policy statement. For the 2026-09-16 decision, the preceding 2026-07-29 statement yields `3.5–3.75%`.
- Retail Sales prefers the same current Census MARTS release PDF because its prose carries the revised/unrevised prior-month change.
- If the current historical release PDF has not propagated on release day, Retail Previous is derived from Census' first-party seasonally adjusted Retail & Food Services total series (`adv44X72.txt`) using the prior two official monthly levels.
- The adjusted-series parser stops before the later `SEASONAL FACTORS` section so factor rows cannot overwrite sales levels.
- If neither current first-party path can support the value, Previous remains blank rather than using a stale prior-release initial value.
- Snapshot runtime installs this resilience layer, and code changes trigger an immediate production refresh.

Validation evidence:

- PR #26 Release Result Resilience Check run `35181315471`, job `105073856424`: success.
- Deterministic release and Previous-value regressions: success.
- First-party live probe:
  - FOMC Actual `3.75–4%`, Previous `3.5–3.75%` from the 2026-07-29 Fed statement.
  - Retail Sales Actual `1.2%`, Previous `-0.5%`, with release-day fallback source `Census MARTS adjusted total series`.
- PR #26 merge-triggered production refresh run `35181398269`: success, including snapshot validation, history persistence and bot commit.
- Post-merge broad Validate public feed run `35181398275`: success, including official-source collector probe.
- Production data bot commit: `41a02abbc0b47a9d68df7bd667367b5bbe094d08`.
- Production snapshot generated `2026-09-17T12:18:22+08:00` contains:
  - Retail Sales 2026-09-16: Actual `1.2%`, Previous `-0.5%`, sales level `$773.9B`.
  - FOMC 2026-09-16: Actual `3.75–4%`, Previous `3.5–3.75%`.
  - Initial Claims and Housing releases retain their existing Previous values.
  - `official_macro_ready = true` and all current source-health flags are true.

## 2026-09-21 Taiwan CBC release incident and recovery

The 2026-09-17 Taiwan CBC event exposed another released-result gap. The dashboard-open dispatch and refresh gate were healthy: a workflow run correctly reported `1 released event(s) still missing actual value: 台灣中央銀行理監事會利率決議`, but the collector returned no changed provider values.

PR #27 (`6a3ed2e7b151d098a7c2ca3bc2d701b8e8084cf6`) fixed the CBC result path without hard-coded rates:

- the stable first-party discount-rate table is parsed for the strict pre-meeting Previous value;
- the dedicated CBC policy-decision listing is searched only for real `cp-357` decision detail pages;
- listing/navigation pages are excluded so they cannot satisfy the meeting-date match accidentally;
- the exact meeting-date decision release is parsed for the discount rate and unchanged-policy wording;
- a nearby newly-effective first-party rate-table row remains a fallback for changed-rate decisions;
- insufficient first-party evidence still fails closed.

Live validation on PR #27 succeeded in run `35585643845`, job `106288229860`:

- event: `official-tw-cbc-2026-09-17`
- Actual: `2%`
- Previous: `2%`
- decision source: `https://www.cbc.gov.tw/tw/cp-357-192864-4319f-1.html`

Post-merge production refresh run `35585809837`, job `106288756822`, succeeded, and broad public-feed validation run `35585809858`, job `106288756656`, also succeeded.

Because the fix landed after the 2026-09-17 event had already aged outside the normal 48-hour public snapshot window, PR #28 (`4dec039d06b10e25e878e12adf34a0829a3edff2`) added a generic first-party CBC history-backfill utility rather than hard-coding production values. PR dry-run validation `35586249698` / `106290170667` succeeded. The post-merge backfill run `35586412002` / `106290683027` re-resolved the official event and appended a `released` history row. Data commit `538b2d4e691b73730e46aa0996879f8085ceb6a6` now records Actual `2%`, Previous `2%`, status `released`, and the official decision URL.

The current `data/latest.json` does not contain the 2026-09-17 CBC event because that is expected under the 48-hour retention contract; the append-only history ledger now preserves the corrected released state.

## Private overlay v1 contract

`market_event_radar/private_overlay.py` remains the producer-side private expectation contract and does not alter the public snapshot.

- `survey_consensus`: may produce `canonical_surprise` only when captured strictly before release.
- `provider_forecast`: may produce only `diagnostic_comparison`; it never fills canonical consensus or canonical Surprise.
- MT5 remains `provider_forecast` and is not promoted merely because MetaTrader calls the field Forecast.

The downstream `investment-dashboard` private consumer and append-only ingestion transport are already merged. The remaining overlay blocker is authentic private pre-release evidence, not the consumer schema.

## Hard boundaries

- Consensus/provider failure must never degrade the official feed.
- Only values captured before release may drive original canonical Surprise.
- Do not key Surprise semantics by metric ID alone.
- Do not call MT5 `forecast` canonical market consensus without repeated validation.
- Do not publicly persist third-party compiled values without clear redistribution rights.
- Do not place consensus retrieval inside Streamlit reruns.
- Do not weaken watchdog/result requirements to hide collector failures.
- Keep official release recovery aligned with the 48-hour public retention window unless the retention contract itself changes.
- For revised economic data, prefer the value/current series published with the current release over a stale Previous copied from an older snapshot.

## Known debt / blockers

- No unattended zero-cost source has earned `survey_consensus` status.
- Authentic private pre-release evidence is still required for end-to-end canonical Surprise validation.
- Historical/private MT5 evidence files are intentionally not committed to this public repository.
- Official collectors remain exposed to future first-party page/schema changes; dedicated live probes now cover the FOMC/Retail result and Previous failure class.
- CBC forward result collection is now live-verified, but all official collectors remain exposed to future first-party HTML/schema changes.
- Dashboard legacy rolling smoke checks can still false-fail independently of producer health.

## Exact next action

Resume authentic private pre-release overlay evidence validation; use provider_forecast only as diagnostic evidence until a true pre-release survey_consensus source is available.


## BOJ meeting/result semantic repair (2026-09-29)

Incident:
- the BOJ official MPM page contains four date columns per row: meeting dates, Outlook release, Summary of Opinions release, and Minutes release;
- the previous parser scanned every date in the whole year section;
- this incorrectly emitted `2026-09-28` (Minutes for the July 30-31 meeting) and `2026-10-01` (Summary of Opinions for the Sept. 17-18 meeting) as new BOJ policy meetings;
- those false events also had `expects_result=false`, so no Actual/Previous could ever appear.

PR #29 repair:
- parse only genuine two-day MPM ranges and use the second meeting day as the canonical event date;
- adjacent single release dates can no longer become policy meetings;
- BOJ policy meetings now set `expects_result=true`;
- after release, fetch the first-party BOJ policy statement PDF;
- canonical Actual is the statement's uncollateralized overnight call-rate guideline;
- Previous is derived from the immediately preceding official MPM statement;
- deterministic regressions cover the Sept. 17-18 / Sept. 28 / Oct. 1 distinction and policy-rate parsing.

First-party verification:
- BOJ's official 2026 table identifies Sept. 17-18 as the September MPM;
- Sept. 28 is the Minutes release for July 30-31;
- Oct. 1 is the Summary of Opinions release for Sept. 17-18;
- the current BOJ guideline is around 1.25%, while the July 31 statement was around 1.0%.

This repair does not alter consensus/private-provider semantics.


## BOJ live acceptance (2026-09-29)

PR #29 was merged and the push-triggered public-feed refresh completed as commit `7864c0d4dc4a51e1e64151c6d9daf032b0e7c349`.

Acceptance evidence:
- `data/latest.json` regenerated at `2026-09-29T09:41:35.320204+08:00`;
- false BOJ policy-meeting events on 2026-09-28 (Minutes release) and 2026-10-01 (Summary of Opinions release) are absent from the public snapshot;
- Work-PC `market-event-radar` checkout fast-forwarded from `63d2ff778480...` to `7864c0d4dc4a...`;
- bounded `investment radar-validate` returned `INVESTMENT_RADAR_VALIDATE_PASS`: schema v2 with 8 valid events.

Conclusion: BOJ schedule semantics are repaired in the canonical producer and the Work-PC backup checkout is reconciled. No downstream dashboard parser workaround is required.


## Korea CPI result-recovery incident — 2026-10-02

Incident:
- the 2026-10-02 Korea CPI event remained `scheduled` with blank Actual/Previous long after its 07:00 TPE release;
- watchdog correctly failed on the overdue Tier-S result, but the smart refresh gate stopped retrying after 12 hours even though released-event retention/watchdog obligations last 48 hours;
- while still inside the old 12-hour window, smart refresh did run but the Korea collector returned no changed values;
- the MODS CPI newsroom had migrated to board `bid=213`, and its current listing uses JavaScript title links / attachment links rather than the older stable title-anchor shape;
- the large MODS listing endpoint was also intermittently unavailable from GitHub hosted runners, including repeated 12-second timeouts.

PR #31 merged as `d011e9d8f2ac5b0ff46901c6b4b8e2992e649472`:
- aligned smart missing-result recovery with the existing 48-hour released-event retention contract;
- moved the Korea CPI result path to the current MODS board;
- added deterministic Korea CPI and recovery-window regressions.
This restored the repair loop but did not yet close the collector incident: the first post-merge production refresh still left Korea CPI blank.

PR #32 merged as `067654012a33a2f36c5a481ee8f2b4542591b1ed`:
- normalizes current MODS JavaScript/plain-title CPI listing layouts through stable `list_no` extraction;
- accepts the MODS newest-item marker without confusing attachment titles with release titles;
- uses bounded retry with fresh cache tokens so an empty cached response cannot freeze the same process;
- prefers first-party KOSIS press-release discovery, then MODS RSS, with the large MODS board HTML retained only as fallback;
- KOSIS is discovery only; released values still come from the official MODS release detail pages;
- Actual is parsed from the newest official CPI release; Previous is parsed from the immediately preceding official CPI release;
- no production release value or release-specific `list_no` is hard-coded;
- added dedicated deterministic regressions plus a live first-party Korea CPI probe to the broad validation workflow.

Live validation:
- PR #32 Validate public feed run `37018125812`: SUCCESS;
- Korea CPI deterministic recovery regressions: 9 PASS;
- live discovery resolved current detail `list_no=447322` and previous detail `list_no=446746`;
- live probe returned Actual `2.9%` and Previous `3.1%`;
- all official-source collector probes passed;
- post-merge Validate public feed run `37018384010`: SUCCESS;
- post-merge production refresh run `37018383976`: SUCCESS;
- production data commit `496949693c049040d5c8543d1ce61d9a12acab0d`;
- production snapshot generated `2026-10-02T22:14:01.954029+08:00`;
- `official-kr-mods-cpi-2026-10-02` is now `released`, Actual `2.9%`, Previous `3.1%`;
- the append-only October history ledger records the same released state;
- `official_macro_ready = true`;
- the simultaneously released US NFP bundle remained intact, confirming this was not a broad feed regression.

Operational conclusion:
- the Event Radar producer is healthy again;
- this incident was an upstream result-recovery/source-resilience failure, not a dashboard presentation failure;
- dashboard consumer semantics did not require a workaround or contract change.

Hard boundaries added by this incident:
- missing-result smart recovery must not expire earlier than the watchdog/released-retention contract;
- do not assume a first-party newsroom title is a normal anchor URL;
- do not depend exclusively on a large first-party HTML listing when the same authority exposes a lighter first-party discovery surface;
- non-empty values from an older release are not sufficient live acceptance: the newest release identity must be verified;
- never hard-code a current Actual/Previous or release-specific board ID to close an incident.

Exact next action:
- return to the pre-existing consensus/surprise roadmap; preserve Korea CPI release recovery as a live regression and let the next scheduled watchdog validate normal unattended operation.


## 2026-10-07｜Taiwan CPI live recovery accepted; ISM remains schedule-only by authorization boundary

Taiwan CPI incident closure:
- dashboard-assisted workflow_dispatch run 37594189687 completed successfully;
- canonical snapshot regenerated at `2026-10-07T16:30:45.620956+08:00`;
- event `official-tw-dgbas-cpi-20261007` is now `released`;
- Actual = `2.73%`;
- Previous = `2.04%`;
- producer data commit = `52ae15dbbc43ae79a8ea13fc845326a0d8e0b259`.
This proves the release-aware orchestration repair successfully woke the producer and the Taiwan CPI first-party collector recovered the released value.

ISM clarification:
- `official-us-ism-services-2026-10-05` remains intentionally schedule-only in the public canonical snapshot;
- current event contract remains `expects_result=false` with tags `schedule-only` and `未接授權數值`;
- investigation confirmed this is not a broken missing-result collector: the existing policy deliberately avoids redistributing ISM PMI index values without an authorized data path;
- PR #33 attempted a first-party result parser but was CLOSED WITHOUT MERGE after live validation surfaced ISM's explicit restriction against recreating/distributing/incorporating PMI index content without written authorization;
- do not publish ISM Actual/Previous into the public repository merely because the values are visible on the ISM website;
- if the user later supplies an authorized/licensed feed or written redistribution permission, implement it as a separately reviewed data-rights-aware path.

Downstream presentation:
- investment-dashboard PR #214 moves the detailed Financial Event Radar into the timed Streamlit fragment and runs the release-aware assist from both 戰情中心 and 股票模組 live fragments;
- this fixes the consumer-side symptom where canonical CPI had already changed but the detailed radar remained visually stale until a full app rerun;
- downstream presentation should explicitly label ISM rows as schedule-only/authorization-limited instead of making them look like failed data retrieval.

Exact next action:
Preserve the public ISM schedule-only boundary; continue with the pre-existing consensus/surprise roadmap unless an authorized ISM data source is supplied.
