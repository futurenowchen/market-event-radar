# Market Event Radar Handoff

Last reconciled: 2026-09-11 Asia/Taipei

## Canonical role

`futurenowchen/market-event-radar` is the standalone producer for unattended market-event snapshots. `futurenowchen/investment-dashboard` is a downstream consumer/presentation layer.

## Verified implementation baseline

Verified code commit: `848dab220427efe0240ea2662c1f19d4b39ed1ce`

At this baseline:

- Official-source-first macro collection is production-capable for the current US/TW/JP/KR high-signal universe.
- Snapshot schema v2 is live.
- `EventMetric` rich release bundles are persisted through snapshots/history.
- US expansion through Phase 4 is merged: PPI, Retail Sales, JOLTS, ECI, Initial Claims, Industrial Production/Capacity Utilization, Durable Goods, Housing Starts/Permits, ISM PMI scheduling, Productivity & Costs, GDP estimate tier calibration, FOMC Minutes, and constrained Fed Chair events.
- Latest observed public snapshot at reconciliation was healthy (`official_macro_ready=true`).
- Dashboard PR #84 already consumes optional rich `metrics` bundles and renders a `關鍵讀數` column.

## Active implementation: PR #16

Branch: `feat/consensus-surprise-v1`
Head at reconciliation: `49c2f02135e6e7e811bca6fce425e69e89974ed8`

Implemented but not yet merged:

- provider-neutral `ConsensusObservation` contract with provider id, provider event id, fetch time, optional PIT/as-of time, release time, raw consensus, unit, and source URL
- strict pre-release eligibility guard for surprise computation
- deterministic `SurpriseResult` engine with per-metric direction, impulse, policy implication, and magnitude thresholds
- initial semantic coverage for inflation, payrolls, unemployment, claims, growth, and wage-pressure families
- optional Trading Economics adapter using survey `Forecast` and explicitly not `TEForecast`
- adapter returns an empty result when `TRADING_ECONOMICS_API_KEY` is absent; official feed health is untouched
- deterministic tests and package exports
- `docs/CONSENSUS_PROVIDER_AUDIT.md`

Validation observed on PR #16 before this handoff update:

- snapshot contract: passed
- package/dependencies: passed
- compile: passed
- event history: passed
- release metrics: passed
- consensus/surprise tests: passed
- Phase 2: passed
- DOL claims parser: passed
- Phase 3: passed
- Phase 4: passed
- package API smoke: passed
- live official-source collector probe: still running at the last observation

Do not merge PR #16 merely because the deterministic portion is green; first inspect the terminal CI result and distinguish a true regression from external-source flakiness if the live probe fails.

## Product direction now locked

Coverage expansion is no longer the primary objective. The next value layer is:

1. **Official layer** — schedule, Actual, Previous, official release metrics. Stable and authoritative.
2. **Consensus layer** — separate optional provider. Must preserve provenance and point-in-time/pre-release eligibility.
3. **Surprise engine** — compute Actual vs eligible Consensus, then semantic direction/magnitude/policy implication.
4. **Event Reaction layer** — later attach market-price response (NASDAQ / yields / USD etc.).

## Consensus provider audit (2026-09-11)

Current preferred first integration target: **Trading Economics**.

Reasoning:

- TE documentation/API contract exposes economic-calendar `Forecast` separately from `Actual` and `Previous` and defines it as consensus from a representative group of economists.
- `TEForecast` is TE's own model/analyst projection and must never be substituted for consensus.
- TE supports historical/point-in-time calendar access suitable for preserving what consensus was known before release.
- EODHD exposes an `estimate` field and remains a possible secondary provider, but the reviewed public documentation does not establish equivalent survey-consensus provenance.

The detailed audit is persisted in `docs/CONSENSUS_PROVIDER_AUDIT.md` on PR #16.

## Consensus architecture requirements

Required record-level provenance:

- provider id
- provider event id / source key when available
- fetched timestamp
- as-of / point-in-time timestamp when supported
- raw consensus string/value
- metric identity mapping
- eligibility: only information known before the official release cutoff may drive surprise

Hard rules:

- Consensus disabled/missing must leave official snapshots valid.
- Provider errors must never flip `official_macro_ready` false.
- Do not silently copy consensus into the official provider's source fields.
- Preserve legacy `forecast` compatibility only through an explicit merge/enrichment step.
- Never use a post-release revised consensus snapshot to compute the original surprise unless it can be proven to represent pre-release consensus.

## Surprise engine requirements

Do not reduce surprise to a sign-only rule.

Retain at minimum:

- numeric surprise in native units / percentage points where parseable
- normalized direction vocabulary appropriate to the metric (`hotter/cooler`, `stronger/weaker`, `higher/lower than expected`)
- economic impulse (`inflation`, `growth`, `labor-tightness`, `labor-weakness`, etc.)
- policy implication where justified (`hawkish`, `dovish`, `mixed`, `neutral/unknown`)
- magnitude bucket (`small`, `medium`, `large`) based on per-metric thresholds, not one global threshold

Initial semantic families prioritize CPI, PPI, Core PCE, NFP payrolls, unemployment rate, Initial Claims, Retail Sales, GDP, and ECI.

## Known debt / caution

- The dashboard repository's old official-backend CI gate can false-fail because it requires specific periodic providers inside a rolling 21-day horizon. This is not evidence of a rich-metrics regression.
- The dashboard's local live fallback still contains an older embedded collector set than this standalone repository; normal operation uses the public standalone snapshot first.
- The collector runtime still uses a legacy internal `MarketEvent` shape and attaches `metrics` dynamically in some paths; the package model already has typed `EventMetric`. Avoid large refactors while adding consensus unless necessary.

## Do not repeat

- Do not re-expand the US event universe before the consensus/surprise layer is proven.
- Do not move consensus retrieval into Streamlit/dashboard reruns.
- Do not make Trading Economics or any paid/external provider a dependency of official feed health.
- Do not infer consensus from Previous.
- Do not use `TEForecast` as survey consensus.
- Do not scrape unattributed finance-calendar numbers and call them market consensus.

## Exact next action

Inspect PR #16's terminal CI result. If the implementation is green, merge PR #16, update `verified_code_commit` in both handoff files to the merged implementation SHA, then begin deterministic internal-event ↔ Trading Economics event/metric mapping and a credentialed canary plan. Do not mutate production snapshots before that contract is proven.
