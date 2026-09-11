# Market Event Radar Handoff

Last reconciled: 2026-09-11 Asia/Taipei

## Canonical role

`futurenowchen/market-event-radar` is the standalone producer for unattended market-event snapshots. `futurenowchen/investment-dashboard` is a downstream consumer/presentation layer.

## Verified implementation baseline

Verified code commit: `e398e17ad39edf3fea06b41a4ab9d6342ee09f5b`

The current merged implementation includes:

- official-source-first macro collection for the current US/TW/JP/KR high-signal universe
- snapshot schema v2 and rich release `metrics`
- US high-signal coverage through Phase 4
- provider-neutral `ConsensusObservation` with explicit provenance and pre-release/PIT eligibility
- deterministic Surprise engine with numeric surprise, semantic direction, magnitude, economic impulse, and policy implication
- event-family + metric-id semantic keys, preventing shared IDs such as `headline_mom` from crossing inflation/growth meanings
- opt-in Trading Economics adapter using survey `Forecast`, never `TEForecast`
- conservative deterministic TE identity mapping for verified CPI, headline PPI, PCE, Employment Situation, Initial Claims, Retail Sales, and ECI metrics
- deliberate non-mapping of core PPI because the official BLS series used by this radar excludes food, energy **and trade services**, while TE's common Core PPI definition is not semantically identical

Dashboard PR #84 already consumes optional rich `metrics`; it does not yet consume consensus/surprise.

## Merge / validation evidence

### PR #16 — Consensus / Surprise foundation

- merge: `1514cf89db3b73683ae6d4db09c0eeb2ac937ed9`
- CI run: `34553881787`
- result: success, including live official-source probe

### PR #17 — Surprise semantic-family hardening

- merge: `d8fac316b1cb694bd981a6781354193edd464f62`
- CI run: `34554223095`
- result: success
- regression coverage proves CPI/PPI/PCE and Retail Sales can reuse metric IDs without borrowing the wrong semantics; unknown family fails closed; ECI uses the collector's real `compensation_qoq` identity

### PR #18 — Trading Economics mapping v1

- merge: `e398e17ad39edf3fea06b41a4ab9d6342ee09f5b`
- CI run: `34554463876`
- result: success
- mapping tests require every mapped metric to have an explicit Surprise semantic rule and preserve deliberate non-mappings

## Product direction

1. **Official layer** — stable: schedule, Actual, Previous, official release metrics.
2. **Consensus layer** — contract + mapping foundation merged; credentialed canary remains.
3. **Surprise engine** — semantic foundation merged; production snapshot enrichment remains.
4. **Event Reaction layer** — later attach post-release market-price response.

Coverage expansion is no longer the main objective. Interpretation depth is.

## Consensus provider decision

First target: **Trading Economics**.

- TE documents `Forecast` as consensus from a representative group of economists.
- `TEForecast` is TE's own projection and must never be used as consensus.
- TE offers point-in-time calendar access suitable for preventing look-ahead bias.
- EODHD remains a possible secondary provider, but its documented `estimate` field has not yet been accepted as equivalent survey consensus.

See `docs/CONSENSUS_PROVIDER_AUDIT.md` and `market_event_radar/consensus_mapping.py`.

## Hard boundaries

- Consensus disabled/missing must leave official snapshots valid.
- Provider errors must never flip `official_macro_ready` false.
- Only consensus known before release may drive the original Surprise.
- Do not put consensus retrieval into Streamlit/dashboard reruns.
- Do not key Surprise semantics by metric ID alone.
- Do not map two metrics merely because their labels look similar.
- Do not use `TEForecast` as survey consensus.
- Do not resume broad macro coverage expansion before this interpretation layer is proven unless explicitly requested.

## Known debt

- Production snapshot schema does not yet persist consensus/surprise fields.
- A credentialed live TE canary has not yet been run.
- Some secondary metrics remain intentionally unmapped until semantic equivalence is verified.
- Dashboard embedded live fallback lags the standalone producer.
- Dashboard legacy event-radar smoke check can false-fail because it requires periodic providers inside a rolling 21-day horizon.

## Exact next action

Run a credentialed **non-production Trading Economics canary** using the mapping registry. Verify returned event identity, units, release-time alignment, provider IDs, pre-release `Forecast`, and point-in-time behavior. Persist that evidence. Only after the canary is verified should consensus/surprise be added to the public snapshot contract and then rendered by the dashboard.
