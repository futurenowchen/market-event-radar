# Market Event Radar Handoff

Last reconciled: 2026-09-11 Asia/Taipei

## Canonical role

`futurenowchen/market-event-radar` is the standalone producer for unattended market-event snapshots. `futurenowchen/investment-dashboard` is the downstream consumer/presentation layer.

## Verified implementation baseline

Verified code commit: `044c3bc10b4bc7dc54227f0c5879efa4a5bf0b1c`

Current merged implementation includes:

- official-source-first macro feed, snapshot schema v2, rich release metrics, and US high-signal coverage through Phase 4
- provider-neutral `ConsensusObservation` with provider provenance and strict pre-release/PIT eligibility
- Surprise engine producing numeric surprise, direction, magnitude, economic impulse, and policy implication
- Surprise semantics keyed by `event_family + metric_id`, so shared IDs such as `headline_mom` cannot borrow the wrong interpretation
- optional Trading Economics adapter using survey `Forecast`, never `TEForecast`
- conservative official-metric ↔ TE indicator registry for verified CPI, headline PPI, PCE, Employment Situation, Initial Claims, Retail Sales, and ECI metrics
- deliberate non-mapping of core PPI because the official series and TE's common Core PPI definition are not semantically identical
- isolated credentialed-canary harness that never writes production snapshots and safely dry-runs when no TE key exists

Dashboard PR #84 already consumes rich `metrics`; it does not yet consume consensus/surprise.

## Merge / validation evidence

- PR #16 — Consensus / Surprise foundation — merge `1514cf89db3b73683ae6d4db09c0eeb2ac937ed9`, CI `34553881787`, success
- PR #17 — semantic-family hardening — merge `d8fac316b1cb694bd981a6781354193edd464f62`, CI `34554223095`, success
- PR #18 — TE mapping v1 — merge `e398e17ad39edf3fea06b41a4ab9d6342ee09f5b`, CI `34554463876`, success
- PR #19 — isolated TE canary — merge `044c3bc10b4bc7dc54227f0c5879efa4a5bf0b1c`, CI `34554747667`, success

PR #19 validation includes deterministic provider-row identity tests, canary helper tests, no-key dry-run, all existing release/mapping/Phase 2-4 tests, package smoke, and the live official-source probe.

## Current product direction

1. **Official layer** — stable.
2. **Consensus layer** — contract, mapping, and canary harness merged; live credentialed provider evidence remains.
3. **Surprise engine** — semantic foundation merged; production persistence remains.
4. **Event Reaction layer** — later attach post-release market-price response.

Coverage expansion is no longer the main objective; interpretation depth is.

## Consensus provider decision

First target: **Trading Economics**.

- TE documents `Forecast` as consensus from a representative group of economists.
- `TEForecast` is TE's own projection and must never be used as consensus.
- TE documents calendar timestamps/identities and point-in-time retrieval suitable for validating pre-release information.
- EODHD remains a possible secondary provider, but its `estimate` field has not yet been accepted as equivalent survey consensus.

See `docs/CONSENSUS_PROVIDER_AUDIT.md`, `market_event_radar/consensus_mapping.py`, and `scripts/canary_trading_economics_consensus.py`.

## Canary behavior

Without `TRADING_ECONOMICS_API_KEY`, the canary prints the exact planned event/metric queries and exits successfully unless `--require-key` is specified.

With a key, it verifies mapped TE rows using indicator identity plus release-time alignment and reports provider calendar ID/ticker, unit, `Forecast`, presence of `TEForecast`, and whether the retrieved observation is currently eligible for Surprise. It never prints the credential and never writes `data/latest.json`.

The canary does **not** treat a post-release current-calendar Forecast as proof of the original pre-release consensus. Point-in-time behavior must be verified before historical Surprise is trusted.

## Hard boundaries

- Consensus disabled/missing must leave official snapshots valid.
- Provider errors must never flip `official_macro_ready` false.
- Only consensus proven known before release may drive original Surprise.
- Do not put consensus retrieval into Streamlit/dashboard reruns.
- Do not key Surprise semantics by metric ID alone.
- Do not map two metrics merely because labels look similar.
- Do not use `TEForecast` as survey consensus.

## Known debt

- A live credentialed TE canary has not yet been run because no API credential is available in this chat/environment.
- Production snapshot schema does not yet persist consensus/surprise fields.
- PIT semantics need credentialed verification.
- Some secondary metrics remain intentionally unmapped.
- Dashboard embedded live fallback lags the standalone producer.
- Dashboard legacy rolling-21-day smoke gate can false-fail.

## Exact next action

Supply `TRADING_ECONOMICS_API_KEY` through a secret-capable environment and run:

`python scripts/canary_trading_economics_consensus.py --snapshot data/latest.json --require-key`

Persist the observed provider IDs/tickers, units, timestamps, Forecast availability, and PIT evidence. Only after that evidence is clean should the public snapshot schema gain consensus/surprise fields and the dashboard render them.
