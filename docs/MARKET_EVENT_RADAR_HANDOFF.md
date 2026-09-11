# Market Event Radar Handoff

Last reconciled: 2026-09-11 Asia/Taipei

## Canonical role

`futurenowchen/market-event-radar` is the standalone producer for unattended official market-event snapshots. `futurenowchen/investment-dashboard` is the downstream consumer/presentation layer.

## Verified implementation baseline

Verified code commit: `044c3bc10b4bc7dc54227f0c5879efa4a5bf0b1c`

Current merged implementation includes:

- official-source-first macro feed, snapshot schema v2, rich release metrics, and US high-signal coverage through Phase 4
- provider-neutral `ConsensusObservation` with provider provenance and strict pre-release/PIT eligibility
- Surprise engine producing numeric surprise, direction, magnitude, economic impulse, and policy implication
- Surprise semantics keyed by `event_family + metric_id`
- optional Trading Economics adapter using survey `Forecast`, never `TEForecast`
- conservative official-metric ↔ TE indicator registry
- deliberate non-mapping of core PPI for semantic-definition mismatch
- isolated TE canary harness that never writes production snapshots and safely dry-runs without credentials

PRs #16-#19 remain green and merged. No implementation commits have occurred after `044c3bc...`; later commits are handoff/provider-audit documentation only.

## Product direction

1. **Official layer** — stable.
2. **Consensus layer** — provider-neutral contract/semantics exist; paid TE is no longer the active deployment target.
3. **Surprise engine** — semantic foundation merged; production/private persistence remains.
4. **Event Reaction layer** — later attach post-release market-price response.

Coverage expansion remains secondary to interpretation depth.

## Zero-cost provider pivot — 2026-09-11

Do **not** purchase Trading Economics for the current personal deployment. Keep TE as the best-documented semantic/reference benchmark only.

The active zero-cost canary path is now:

1. **MetaTrader 5 Economic Calendar** as the primary machine-readable forecast source candidate.
2. **Myfxbook Economic Calendar** as a free cross-check because its calendar explicitly labels `Previous`, `Consensus`, and `Actual`.
3. Promote an MT5 `forecast` to our canonical `consensus` only after repeated event/metric/time/unit/value agreement. Until then call it `provider_forecast`.

### Why MT5

MetaQuotes documents that MetaTrader 5 is free to download, demo accounts require no investment and provide platform functionality for testing, and the built-in Economic Calendar exposes current/forecast/previous macro values. The supported MQL5 calendar API exposes programmatic event/value/history functions including `CalendarValueHistory` and `CalendarValueLast`.

Important constraint: calendar functions are native MQL5 terminal functions; the normal Python `MetaTrader5` package does not expose them. The intended bridge is a small MQL5 Service/EA that writes a private/local JSON or CSV file consumed by Python.

See `docs/CONSENSUS_PROVIDER_AUDIT.md` for evidence and references.

## Licensing / data-placement boundary

Free access does not imply unrestricted redistribution.

Until redistribution rights for a third-party calendar are explicit:

- keep public `market-event-radar` snapshots official-source-only;
- keep vendor forecast/consensus values in a **private runtime overlay** for personal use;
- retain open-source mapping, normalization, Surprise semantics, and provider adapter code in the public repo where appropriate;
- let the private `investment-dashboard` consume official public data plus the private overlay.

Do not put vendor forecast values into `data/latest.json` merely because they are obtainable for free.

## Provider status

### Trading Economics

Best semantic benchmark: its docs explicitly define `Forecast` as consensus from a representative group of economists and separate proprietary `TEForecast`. Existing adapter/mapping/canary remain useful reference code. Paid access is not justified for this deployment.

### MetaTrader 5

Primary zero-cost canary candidate. Supported terminal API gives forecast/previous/actual/history fields. Survey methodology/provenance is not documented as precisely as TE, so validate before labelling values as `consensus`.

### Myfxbook

Useful free human-readable/export cross-check with an explicit `Consensus` column. Do not rely on undocumented internal endpoints for unattended production; the reviewed official API does not document Economic Calendar access.

### Forex Factory

Excluded from automated persistence/publication: its notices prohibit copying/republication/redistribution of the calendar/FEED compilation without written consent.

### Finnhub

Excluded from zero-cost path: Economic Calendar is documented as Premium Access Required.

### EODHD / FMP

Remain secondary probes only. Current evidence does not establish both free-tier entitlement and survey-consensus provenance strongly enough to make either the primary path.

## Hard boundaries

- Consensus missing/provider failure must never degrade the official feed.
- Only data captured before release may drive the original Surprise.
- Do not key Surprise semantics by metric ID alone.
- Do not map metrics just because labels look similar.
- Do not call a generic forecast `consensus` until validated.
- Do not publicly persist third-party compiled values without clear redistribution rights.
- Do not place consensus retrieval into Streamlit reruns.

## Known debt

- No MT5 calendar bridge exists yet.
- MT5 forecast-to-consensus equivalence still needs empirical validation.
- Production/public snapshot schema still intentionally has no consensus/surprise fields.
- A private overlay contract/consumer path has not yet been implemented.
- Dashboard embedded live fallback lags the standalone producer.
- Dashboard legacy rolling-21-day smoke gate can false-fail.

## Exact next action

Build an isolated **MetaTrader 5 / MQL5 Economic Calendar export canary** for the smallest useful high-signal set (CPI, PPI headline, Initial Claims). It must write only private/local canary output, preserve event/value IDs, forecast/previous/actual, unit, release time and capture time, and must not modify `data/latest.json`. Then compare upcoming pre-release MT5 forecasts against Myfxbook's explicitly labelled Consensus before promoting the source to the production/private Consensus layer.