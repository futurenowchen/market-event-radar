# Market Event Radar Handoff

Last reconciled: 2026-09-11 Asia/Taipei

## Canonical role

`futurenowchen/market-event-radar` is the standalone producer for unattended market-event snapshots. `futurenowchen/investment-dashboard` is a downstream consumer/presentation layer.

## Verified implementation baseline

Verified code commit: `1514cf89db3b73683ae6d4db09c0eeb2ac937ed9`

At this baseline:

- Official-source-first macro collection is production-capable for the current US/TW/JP/KR high-signal universe.
- Snapshot schema v2 is live.
- `EventMetric` rich release bundles are persisted through snapshots/history.
- US expansion through Phase 4 is merged.
- Dashboard PR #84 already consumes optional rich `metrics` bundles and renders a `關鍵讀數` column.
- PR #16, **Add consensus and surprise foundation**, is merged.

## Consensus / Surprise foundation now merged

PR #16 added:

- provider-neutral `ConsensusObservation`
- provider id / provider event id / fetch time / optional PIT-as-of / release time / raw consensus / unit / source URL provenance
- strict rule that only information known before release is eligible for surprise computation
- deterministic `SurpriseResult` with numeric surprise, direction, magnitude, economic impulse, and policy implication
- initial semantic rules for inflation, payrolls, unemployment, claims, growth, and wage-pressure families
- opt-in Trading Economics adapter
- explicit use of TE `Forecast` as survey consensus and rejection of `TEForecast` as consensus
- no-credential behavior that returns no consensus instead of degrading the official feed
- deterministic consensus/surprise tests and public package exports
- `docs/CONSENSUS_PROVIDER_AUDIT.md`

## Validation evidence

PR #16 feature head: `49c2f02135e6e7e811bca6fce425e69e89974ed8`
Merge commit: `1514cf89db3b73683ae6d4db09c0eeb2ac937ed9`
GitHub Actions run: `34553881787`
Result: **success**

Passed checks included:

- snapshot contract
- package/dependency install
- compile
- event history
- release metrics
- consensus/surprise tests
- Phase 2 events
- DOL claims parser
- Phase 3 events
- Phase 4 event policy
- package API smoke
- live official-source collector probe

## Product direction

Coverage expansion is no longer the primary objective. The next layers remain:

1. **Official layer** — schedule, Actual, Previous, official release metrics. Stable.
2. **Consensus layer** — separate optional provider with provenance/PIT controls. Foundation merged; live mapping/canary remains.
3. **Surprise engine** — foundation merged; production enrichment remains.
4. **Event Reaction layer** — later attach post-release market-price response.

## Consensus provider decision

First target: **Trading Economics**.

Reasons:

- TE documents `Forecast` as consensus from a representative group of economists.
- TE keeps `TEForecast` separate as its own projection; never use it as consensus.
- TE supports point-in-time calendar access for preserving pre-release information and avoiding look-ahead bias.
- EODHD remains a possible secondary provider, but its documented `estimate` field has not yet been accepted as equivalent survey consensus.

See `docs/CONSENSUS_PROVIDER_AUDIT.md`.

## Hard boundaries

- Consensus disabled/missing must leave official snapshots valid.
- Provider errors must never flip `official_macro_ready` false.
- Do not put consensus retrieval into Streamlit/dashboard reruns.
- Do not infer consensus from Previous.
- Do not use post-release consensus revisions for original surprise unless PIT evidence proves the value was known before release.
- Do not use `TEForecast` as survey consensus.
- Do not resume broad macro coverage expansion before this interpretation layer is proven unless explicitly requested.

## Known debt

- Dashboard legacy event-radar smoke checks can false-fail because they require periodic providers inside a rolling 21-day horizon.
- Dashboard embedded live fallback lags standalone collector coverage.
- Production snapshot schema does not yet persist consensus/surprise fields.
- The collector runtime still has a legacy internal `MarketEvent` shape in some paths; avoid a large refactor unless required.

## Exact next action

Build and test deterministic mappings between current high-signal internal event/metric identities and Trading Economics calendar identities. Then prepare a credentialed canary that remains isolated from production snapshots. Only after that canary is verified should consensus/surprise be persisted into the public snapshot and exposed in the dashboard.
