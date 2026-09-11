# Market Event Radar Handoff

Last reconciled: 2026-09-11 Asia/Taipei

## Canonical role

`futurenowchen/market-event-radar` is the standalone producer for unattended official market-event snapshots. `futurenowchen/investment-dashboard` is the downstream consumer/presentation layer.

## Verified implementation baseline

Verified code commit: `e89c24f71ddbd0f493e40e19517c6ace57cb5c36`

Current merged implementation includes:

- official-source-first macro feed, snapshot schema v2, rich release metrics, and US high-signal coverage through Phase 4
- provider-neutral `ConsensusObservation` with strict pre-release/PIT eligibility
- deterministic Surprise engine keyed by `event_family + metric_id`
- optional Trading Economics adapter/mapping/canary retained as a paid BYO-credential reference path
- zero-cost MetaTrader 5 canary parser and private/local CLI
- MQL5 Service source for exporting Economic Calendar values to terminal common-files storage
- conservative MT5 identity mapping for CPI, headline PPI, and Initial Claims
- deliberate fail-closed handling for Core PPI semantic mismatch
- no third-party forecast/consensus values written into public `data/latest.json`

## Merge / validation evidence

- PR #16 — Consensus / Surprise foundation — merge `1514cf89db3b73683ae6d4db09c0eeb2ac937ed9`, CI `34553881787`, success
- PR #17 — semantic-family hardening — merge `d8fac316b1cb694bd981a6781354193edd464f62`, CI `34554223095`, success
- PR #18 — TE mapping v1 — merge `e398e17ad39edf3fea06b41a4ab9d6342ee09f5b`, CI `34554463876`, success
- PR #19 — isolated TE canary — merge `044c3bc10b4bc7dc54227f0c5879efa4a5bf0b1c`, CI `34554747667`, success
- PR #20 — zero-cost MT5 consensus canary — merge `e89c24f71ddbd0f493e40e19517c6ace57cb5c36`, CI `34558404985`, success

PR #20 CI validates:

- Python compilation for the MT5 parser/CLI
- deterministic MT5 export fixture parsing
- pre-release capture eligibility
- official snapshot event/metric matching
- Core PPI fail-closed behavior
- all prior consensus/surprise and Phase 2-4 regressions
- package smoke
- live official-source probe

The MQL5 Service source cannot be compiled on the Ubuntu GitHub runner. **Real MetaTrader 5 / MetaEditor compilation and runtime calendar access remain an explicit deployment-side verification step.**

## Product direction

1. **Official layer** — stable and public.
2. **Consensus layer** — public provider-neutral interface; paid adapters are opt-in; maintainer runtime follows zero-cost private-overlay path.
3. **Surprise engine** — semantic foundation merged; private runtime persistence remains.
4. **Event Reaction layer** — later attach post-release market-price response.

Coverage expansion remains secondary to interpretation depth.

## Public / private provider policy

The public project may keep optional paid-provider adapters such as Trading Economics. Users who want commercial survey consensus supply their own credentials/subscription.

The maintainer's personal deployment should not incur recurring consensus-data fees while a validated zero-cost path remains viable.

Therefore:

- public repo keeps official-source data, provider-neutral contracts, Surprise logic, mappings, and optional provider adapters;
- public repo never embeds vendor credentials;
- public `data/latest.json` remains official-source-only unless third-party redistribution rights are explicit;
- maintainer private runtime uses MT5/provider data only in a private/local overlay;
- private `investment-dashboard` may later consume official public data plus that private overlay;
- do not delete a useful paid adapter merely because the maintainer does not subscribe.

## Zero-cost MT5 canary — implementation now merged

Files added by PR #20:

- `mt5/Services/MarketEventRadarCalendarExport.mq5`
- `market_event_radar/providers/mt5_calendar.py`
- `scripts/canary_mt5_consensus.py`
- `scripts/test_mt5_consensus_canary.py`
- `scripts/test_canary_mt5_cli.py`

The MQL5 Service:

- queries MetaTrader 5 Economic Calendar through supported MQL5 calendar functions;
- exports event/value IDs, code/name, sector, importance, unit, multiplier, digits, source URL, release/period times, forecast, previous, revised previous, and actual;
- records terminal server time, GMT time, and inferred server UTC offset;
- writes through `FILE_COMMON` to a private/local JSON file using a temp-file + move pattern;
- defaults to US/USD, price/jobs sectors, 48-hour lookback and 14-day lookahead;
- does not write to this repository or `data/latest.json`.

The Python canary:

- validates export schema/provider identity;
- normalizes MT5 release time to UTC;
- maps only explicitly accepted event names;
- calls MT5 values `provider_forecast`, **not** `consensus`;
- matches against the official snapshot by provider family + release time + metric ID;
- reports whether the value was captured before release;
- can optionally write private local evidence JSON;
- always reports `promotion_status = NOT_PROMOTED` until repeated cross-source evidence justifies promotion.

## Immediate real-world canary opportunity

The current official snapshot schedules US CPI for **2026-09-11 20:30 Asia/Taipei**. This is a useful pre-release validation window.

Myfxbook currently exposes Consensus-labelled CPI expectations that can be used as a human cross-check. Those third-party values must **not** be committed to the public repo; retain cross-check evidence privately.

A successful first live canary should establish:

- MQL5 Service compiles in MetaEditor;
- service can access calendar rows on the selected MT5 demo/broker terminal;
- expected CPI rows are present with stable event/value IDs, units and release time;
- forecast is captured before 20:30 TPE;
- Python CLI matches the MT5 rows to `official-us-bls-cpi-2026-09-11`;
- MT5 values can be compared privately with the same-release Myfxbook Consensus labels.

One successful CPI match is useful evidence but is **not enough** to promote MT5 forecast to canonical survey consensus. Repeat across multiple releases/families before promotion.

## Provider status

### Trading Economics

Best semantic benchmark. Existing adapter/mapping/canary remains available for public BYO-subscription use; it is not required for the maintainer's personal runtime.

### MetaTrader 5

Primary zero-cost machine canary. Parser/CLI/exporter source is merged. Real terminal compile/runtime verification is the current blocker.

### Myfxbook

Free human-readable/export cross-check with explicit `Consensus` labels. Do not depend on undocumented internal endpoints for unattended production.

### Forex Factory

Excluded from automated persistence/publication because its notices restrict copying/republication/redistribution of calendar/FEED compilation without permission.

### Finnhub

Excluded from zero-cost path because Economic Calendar requires Premium access.

### EODHD / FMP

Secondary probes only; free entitlement plus survey-consensus provenance remains insufficiently established.

## Hard boundaries

- Consensus missing/provider failure must never degrade official feed health.
- Only values captured before release may drive original Surprise.
- Do not key Surprise semantics by metric ID alone.
- Do not map metrics just because labels look similar.
- Do not call MT5 `forecast` canonical market consensus until repeated validation supports it.
- Do not publicly persist third-party compiled values without clear redistribution rights.
- Do not place consensus retrieval inside Streamlit reruns.
- Do not require a paid provider for maintainer runtime while the zero-cost path remains viable.

## Known debt / blockers

- MQL5 Service has not yet been compiled in a real MetaEditor/MT5 installation.
- No live MT5 Economic Calendar export has yet been captured.
- MT5 forecast-to-survey-consensus equivalence still requires repeated cross-source evidence.
- Private consensus/surprise overlay contract and dashboard consumer path are not yet implemented.
- public snapshot intentionally has no third-party consensus/surprise values.
- dashboard embedded live fallback lags standalone collector coverage.
- dashboard legacy rolling-21-day smoke gate can false-fail.

## Exact next action

**Compile and run `mt5/Services/MarketEventRadarCalendarExport.mq5` in a real MetaTrader 5 terminal before the 2026-09-11 20:30 TPE CPI release, then run `scripts/canary_mt5_consensus.py` on the private/local export and preserve that pre-release evidence privately.**
