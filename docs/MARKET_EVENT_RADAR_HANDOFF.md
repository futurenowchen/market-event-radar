# Market Event Radar Handoff

Last reconciled: 2026-09-17 Asia/Taipei

## Canonical role

`futurenowchen/market-event-radar` is the standalone producer for unattended official market-event snapshots. `futurenowchen/investment-dashboard` is the downstream consumer/presentation layer.

## Verified implementation baseline

Verified code commit: `d7f2307a9d56aa88c8acf4e713e3ec46df7c09ce`

Later bot commits that only refresh `data/latest.json` / history are expected and do not change this implementation baseline.

Current merged implementation includes:

- official-source-first macro feed, snapshot schema v2, rich release metrics, and US high-signal coverage through Phase 4
- provider-neutral `ConsensusObservation` with strict pre-release/PIT eligibility
- deterministic Surprise engine keyed by `event_family + metric_id`
- optional Trading Economics adapter/mapping/canary retained as a paid BYO-credential reference path
- zero-cost MetaTrader 5 canary parser/private CLI and Windows deployment helper
- PR #23 private overlay v1 with strict `survey_consensus` versus `provider_forecast` semantics
- public `data/latest.json` remains official-source-only
- PR #24 / #25 release-result resilience for FOMC and Census Retail Sales
- official result retry / producer lookback aligned to the same 48-hour horizon used by snapshot retention and watchdog validation

## 2026-09-17 result-collector incident and recovery

The dashboard-open trigger and GitHub Actions scheduler were not the root cause. A dashboard-open `workflow_dispatch` successfully ran the refresh gate and correctly detected a released FOMC event with missing Actual, but the collector returned `No provider values changed`. The scheduled watchdog also correctly failed on two overdue official results: 2026-09-16 Retail Sales and the 2026-09-16 FOMC decision.

Root causes:

1. The FOMC calendar parser flattened the Fed calendar and accepted standalone month/day text, so `Minutes Released ...` dates could become fake FOMC decisions.
2. The federal-funds result parser accepted decimal ranges only and missed mixed-fraction Fed statement text such as `3-3/4 to 4 percent`.
3. Census `retail/sales.html` can lag the current release while the first-party Census Economic Indicators widget already exposes the current MARTS headline.
4. Smart missing-result retries stopped after 12 hours while the public snapshot/watchdog retain releases for 48 hours, leaving a 12h–48h unrecoverable gap.

PR #24 (`402c69f167f18373f0ec4cd9dce0d0f1ecd3259c`) added `v2_event_official_release_resilience.py` and:

- parses only genuine two-day FOMC meeting ranges, preventing minutes-release dates from becoming fake meetings;
- parses decimal and mixed-fraction target ranges;
- adds a first-party Census Economic Indicators fallback for released Retail Sales with exact reference-month validation;
- expands producer/smart-refresh result recovery to 48 hours;
- adds deterministic regression tests and a first-party live probe.

PR #25 (`d7f2307a9d56aa88c8acf4e713e3ec46df7c09ce`) fixed the final Retail runtime edge by using the canonical Census widget URL directly and upgraded the live probe to exercise the integrated `_retail_metrics_resilient()` path end-to-end.

Validation evidence:

- PR #24 Release Result Resilience Check run `35179237457`, job `105067613437`: success.
- Live probe parsed the official 2026-09-16 FOMC target range as `3.75–4%` and the current Census widget successfully.
- Post-PR #24 production refresh recovered FOMC and removed the spurious consecutive FOMC events.
- PR #25 Release Result Resilience Check run `35179613482`, job `105068748995`: success.
- PR #25 integrated live probe produced Retail Sales primary Actual `1.2%` for reference month August 2026.
- Post-merge refresh run `35179685319`: success; snapshot validation, history persistence and bot commit all succeeded.
- Production snapshot generated `2026-09-17T11:51:16+08:00` now contains:
  - Retail Sales 2026-09-16: released, Actual `1.2%`, sales level `$773.9B`.
  - FOMC 2026-09-16: released, Actual `3.75–4%`.
  - no fake FOMC meetings on the minutes-release dates that previously polluted the horizon.

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

## Known debt / blockers

- No unattended zero-cost source has earned `survey_consensus` status.
- Authentic private pre-release evidence is still required for end-to-end canonical Surprise validation.
- Historical/private MT5 evidence files are intentionally not committed to this public repository.
- The broad official collector still depends on upstream first-party page structures; the new live release probe now covers the specific FOMC/Retail failure class.
- Dashboard legacy rolling smoke checks can still false-fail independently of producer health.

## Exact next action

Observe the next scheduled released-result cycle and watchdog (including the 2026-09-17 Taiwan CBC and U.S. evening releases) and verify that released events populate Actual within the 48-hour recovery contract without creating duplicate/spurious calendar events; once that stays green, resume authentic private-overlay evidence validation.
