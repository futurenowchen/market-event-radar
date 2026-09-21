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
