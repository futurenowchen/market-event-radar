# Market Event Radar Handoff

Last reconciled: 2026-09-14 Asia/Taipei

## Canonical role

`futurenowchen/market-event-radar` is the standalone producer for unattended official market-event snapshots. `futurenowchen/investment-dashboard` is the downstream consumer/presentation layer.

## Verified implementation baseline

Verified code commit: `640c8a0fd23e346a1dd244621b2c1cc02b5c7694`

Current merged implementation includes:

- official-source-first macro feed, snapshot schema v2, rich release metrics, and US high-signal coverage through Phase 4
- provider-neutral `ConsensusObservation` with strict pre-release/PIT eligibility
- deterministic Surprise engine keyed by `event_family + metric_id`
- optional Trading Economics adapter/mapping/canary retained as a paid BYO-credential reference path
- zero-cost MetaTrader 5 canary parser and private/local CLI
- MQL5 Service source for exporting Economic Calendar values to terminal common-files storage
- conservative MT5 identity mapping for CPI, headline PPI, and Initial Claims, with Core PPI deliberately fail-closed
- Windows PowerShell deployment helper and live MT5 verification on the company Windows machine
- PR #23 private overlay v1: explicit `survey_consensus` versus `provider_forecast`, with canonical Surprise restricted to eligible pre-release survey consensus
- MT5/provider forecasts are hard-locked to diagnostic comparison only and cannot silently become canonical market consensus
- public `data/latest.json` remains official-source-only and contains no third-party forecast/consensus values

## Merge / validation evidence

- PR #16 — Consensus / Surprise foundation — merge `1514cf89db3b73683ae6d4db09c0eeb2ac937ed9`, CI `34553881787`, success
- PR #17 — semantic-family hardening — merge `d8fac316b1cb694bd981a6781354193edd464f62`, CI `34554223095`, success
- PR #18 — TE mapping v1 — merge `e398e17ad39edf3fea06b41a4ab9d6342ee09f5b`, CI `34554463876`, success
- PR #19 — isolated TE canary — merge `044c3bc10b4bc7dc54227f0c5879efa4a5bf0b1c`, CI `34554747667`, success
- PR #20 — zero-cost MT5 consensus canary — merge `e89c24f71ddbd0f493e40e19517c6ace57cb5c36`, CI `34558404985`, success
- PR #21 — Windows MT5 deployment helper — merge `7dfcf7c4b63711f49a6e33bd92131bcde606acbb`, CI `34559135551`, success
- PR #22 — Windows PS5 helper + multilingual MT5 event mapping — merge `6b4d7422aab172f13fe5663aaaf297fc3a4bae25`
- PR #23 — private consensus / Surprise overlay v1 — merge `640c8a0fd23e346a1dd244621b2c1cc02b5c7694`, CI `34829104766`, success

## Private overlay v1 contract

`market_event_radar/private_overlay.py` is the producer-side contract for private expectation data. It does not change the public snapshot.

Two value kinds are intentionally distinct:

- `survey_consensus`: may produce `canonical_surprise` only when captured strictly before release.
- `provider_forecast`: may produce only `diagnostic_comparison`; it never fills canonical consensus or canonical Surprise.

The builder:

- matches by exact official event ID, official provider and metric ID;
- fails closed on event/provider/metric mismatch;
- reuses the existing `(event_family, metric_id)` Surprise semantic rules;
- rejects post-release observations for original Surprise/comparison;
- serializes stable rounded numeric differences;
- can normalize MT5 canary reports but preserves MT5 as `provider_forecast`;
- writes only to a caller-selected private/local output path through `scripts/build_private_overlay.py`.

`private_runtime/` remains gitignored. Third-party values are not committed to or emitted by the public production snapshot.

## Public / private provider policy

The public project keeps official-source data, provider-neutral contracts, Surprise logic, mappings, and optional provider adapters. Credentials are never embedded.

The maintainer private runtime may combine the public official snapshot with private provider evidence. A provider failure or missing private overlay must never affect `official_macro_ready` or make the official feed unavailable.

Trading Economics remains the strongest semantic reference / BYO-subscription adapter. The maintainer does not need to pay for it while a useful zero-cost research path remains available.

MT5 remains the primary zero-cost machine canary, but its generic Forecast field is not canonical survey consensus. Live CPI cross-checks against Myfxbook showed material divergence on headline measures, so promotion remains prohibited without repeated evidence.

## Hard boundaries

- Consensus missing/provider failure must never degrade official feed health.
- Only values captured before release may drive original canonical Surprise.
- Do not key Surprise semantics by metric ID alone.
- Do not map metrics merely because labels look similar.
- Do not call MT5 `forecast` canonical market consensus until repeated validation supports it.
- Do not display provider forecast as survey consensus in the dashboard.
- Do not publicly persist third-party compiled values without clear redistribution rights.
- Do not place consensus retrieval inside Streamlit reruns.
- Do not require a paid provider for maintainer runtime while the zero-cost path remains viable.

## Known debt / blockers

- Dashboard private-overlay consumer/read path is not yet implemented.
- A durable private persistence/transport path from producer output to the private dashboard is not yet live-validated.
- MT5 forecast-to-survey-consensus equivalence still requires repeated cross-source evidence across multiple releases.
- No unattended zero-cost source has yet earned `survey_consensus` status.
- Historical/private MT5 evidence files are intentionally not committed to this public repository.
- dashboard embedded live fallback lags standalone collector coverage.
- dashboard legacy rolling-21-day smoke gate can false-fail.

## Exact next action

Implement and validate a fail-closed, backward-compatible private overlay consumer in `investment-dashboard` that leaves official event rendering unchanged when no private overlay exists and never labels `provider_forecast` as market consensus.
