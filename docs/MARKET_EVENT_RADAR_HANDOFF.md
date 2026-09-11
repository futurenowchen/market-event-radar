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

## Product direction now locked

Coverage expansion is no longer the primary objective. The next value layer is:

1. **Official layer** — schedule, Actual, Previous, official release metrics. Stable and authoritative.
2. **Consensus layer** — separate optional provider. Must preserve provenance and point-in-time/pre-release eligibility.
3. **Surprise engine** — compute Actual vs eligible Consensus, then semantic direction/magnitude/policy implication.
4. **Event Reaction layer** — later attach market-price response (NASDAQ / yields / USD etc.).

## Consensus provider audit (2026-09-11)

Current preferred first integration target: **Trading Economics**.

Reasoning:

- TE documentation/API contract exposes economic-calendar `Forecast` separately from `Actual` and `Previous` and describes forecast/consensus values as survey-based expectations.
- TE supports historical/point-in-time querying suitable for preserving what consensus was known before release.
- This is materially preferable to treating an opaque provider `estimate` field as survey consensus.

Secondary/fallback providers may be evaluated later, but must not be labelled `consensus` unless provenance and semantics are explicit.

## Consensus architecture requirements

The first implementation must be provider-neutral and safe when no credentials exist.

Required record-level provenance:

- provider id
- provider event id / source key when available
- fetched timestamp
- as-of / point-in-time timestamp when supported
- raw consensus string/value
- metric identity mapping
- eligibility: must be captured before the official release cutoff for surprise computation

Hard rules:

- Consensus disabled/missing must leave official snapshots valid.
- Provider errors must never flip `official_macro_ready` false.
- Do not silently copy consensus into the official provider's source fields.
- Preserve legacy `forecast` compatibility only through an explicit merge/enrichment step.
- Never use a post-release revised consensus snapshot to compute the original surprise unless it can be proven to represent the pre-release consensus.

## Surprise engine requirements

Do not reduce surprise to a sign-only rule.

At minimum retain:

- numeric surprise in native units / percentage points where parseable
- normalized direction vocabulary appropriate to the metric (`hotter/cooler`, `stronger/weaker`, `higher/lower than expected`)
- economic impulse (`inflation`, `growth`, `labor-tightness`, `labor-weakness`, etc.)
- policy implication where justified (`hawkish`, `dovish`, `mixed`, `neutral/unknown`)
- magnitude bucket (`small`, `medium`, `large`) based on per-metric thresholds, not one global threshold

Initial semantic families should prioritize CPI, PPI, Core PCE, NFP payrolls, unemployment rate, Initial Claims, Retail Sales, GDP, and ECI.

## Known debt / caution

- The dashboard repository's old official-backend CI gate can false-fail because it requires specific periodic providers inside a rolling 21-day horizon. This is not evidence of a rich-metrics regression.
- The dashboard's local live fallback still contains an older embedded collector set than this standalone repository; normal operation uses the public standalone snapshot first.
- The collector runtime still uses a legacy internal `MarketEvent` shape and attaches `metrics` dynamically in some paths; the package model already has typed `EventMetric`. Avoid large refactors while adding consensus unless necessary.

## Do not repeat

- Do not re-expand the US event universe before the consensus/surprise layer is proven.
- Do not move consensus retrieval into Streamlit/dashboard reruns.
- Do not make Trading Economics or any paid/external provider a dependency of official feed health.
- Do not infer consensus from Previous.
- Do not scrape unattributed finance-calendar numbers and call them market consensus.

## Exact next action

Implement the provider-neutral consensus domain model + surprise semantics with deterministic tests, then add an opt-in Trading Economics adapter that is inert without credentials. Do not wire credentials or mutate production snapshots until the contract/tests are green.
