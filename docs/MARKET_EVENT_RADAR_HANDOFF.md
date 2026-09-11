# Market Event Radar Handoff

Last reconciled: 2026-09-11 Asia/Taipei

## Canonical role

`futurenowchen/market-event-radar` is the standalone producer for unattended official market-event snapshots. `futurenowchen/investment-dashboard` is the downstream consumer/presentation layer.

## Verified implementation baseline

Verified code commit: `e9087d71db8046fb594de2b6d306b036553f7b54`

Current merged implementation includes:

- official-source-first macro feed, snapshot schema v2, rich release metrics, and US high-signal coverage through Phase 4
- provider-neutral `ConsensusObservation` with strict pre-release/PIT eligibility
- deterministic Surprise engine keyed by `event_family + metric_id`
- optional Trading Economics adapter/mapping/canary retained as a paid BYO-credential reference path
- zero-cost MetaTrader 5 canary parser and private/local CLI
- MQL5 Service source for exporting Economic Calendar values to terminal common-files storage
- conservative MT5 identity mapping for CPI, headline PPI, and Initial Claims (supporting language-invariant `event_code` and Chinese locale)
- deliberate fail-closed handling for Core PPI semantic mismatch
- Windows PowerShell deployment helper and Windows deployment runbook
- live MT5 deployment verified on Windows Work PC (MetaEditor 0 errors, active MQL5 export, 5 pre-release matches)
- no third-party forecast/consensus values written into public `data/latest.json`

## Merge / validation evidence

- PR #16 — Consensus / Surprise foundation — merge `1514cf89db3b73683ae6d4db09c0eeb2ac937ed9`, CI `34553881787`, success
- PR #17 — semantic-family hardening — merge `d8fac316b1cb694bd981a6781354193edd464f62`, CI `34554223095`, success
- PR #18 — TE mapping v1 — merge `e398e17ad39edf3fea06b41a4ab9d6342ee09f5b`, CI `34554463876`, success
- PR #19 — isolated TE canary — merge `044c3bc10b4bc7dc54227f0c5879efa4a5bf0b1c`, CI `34554747667`, success
- PR #20 — zero-cost MT5 consensus canary — merge `e89c24f71ddbd0f493e40e19517c6ace57cb5c36`, CI `34558404985`, success
- PR #21 — Windows MT5 deployment helper — merge `7dfcf7c4b63711f49a6e33bd92131bcde606acbb`, CI `34559135551`, success
- Commit `e9087d7` — multilingual `event_code` mapping and PS5 helper fix — verified locally on live MT5 build 6191.

Real MetaTrader 5 / MetaEditor compilation and runtime calendar access have been **fully verified on the company Windows machine**.

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

## Zero-cost MT5 canary

Files merged by PR #20:

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
- contains no trade/order API calls;
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

## Company Windows deployment path — live verified

The canary was deployed and verified on the maintainer's company Windows Work PC on 2026-09-11.

Verification evidence:

1. **MT5 Terminal**: MetaTrader 5 build 6191 installed at `C:\Program Files\MetaTrader 5\terminal64.exe`. Demo account `112474572` active on `MetaQuotes-Demo`.
2. **Service Installation**: `scripts/install_mt5_canary.ps1` executed cleanly (PS5.1 param initialization bug resolved). Service copied to `AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Services\MarketEventRadarCalendarExport.mq5`.
3. **Compilation**: Compiled via MetaEditor 64-bit (`metaeditor64.exe`). Result: **0 errors, 0 warnings**.
4. **Service Execution**: Service started in MT5 Navigator. Terminal logs confirm periodic export (`wrote 32 rows`).
5. **Private Export**: JSON written atomically to `AppData\Roaming\MetaQuotes\Terminal\Common\Files\MarketEventRadar\mt5_calendar_latest.json`.
6. **Multilingual Adaptation**: MetaQuotes calendar returns localized names on Chinese Windows (e.g. `CPI 年率y/y`). Added language-invariant `event_code` lookup (`consumer-price-index-yy`, etc.) with fallback to localized names.
7. **Downstream Python Canary CLI**:
   - `candidate_observation_count`: 8
   - `matched_official_count`: 8
   - `pre_release_match_count`: 5
   - `promotion_status`: `NOT_PROMOTED`
8. **Tonight's CPI Pre-release Capture (2026-09-11 20:30 Asia/Taipei)**:
   - Captured at 12:39 Asia/Taipei (server GMT+3 offset correctly resolved)
   - Headline YoY: `2.7%` (official prev `3.4%`, captured before release)
   - Headline MoM: `0.0%` (official prev `0.1%`, captured before release)
   - Core YoY: `2.3%` (official prev `2.5%`, captured before release)
   - Core MoM: `0.2%` (official prev `0.2%`, captured before release)
9. **Core PPI Fail-Closed**: `producer-price-index-ex-food-energy-*` intentionally unmapped and excluded from candidates due to BLS trade services exclusion mismatch.
10. **Myfxbook Private Cross-Check**:
    - Core MoM: `0.2%` (MT5 matches Myfxbook `0.2%`)
    - Core YoY: `2.3%` (MT5) vs `2.4%` (Myfxbook)
    - Headline YoY: `2.7%` (MT5) vs `3.4%` (Myfxbook)
    - Headline MoM: `0.0%` (MT5) vs `0.4%` (Myfxbook)
    - Divergence confirms policy: MT5 forecast is `provider_forecast`, not survey consensus. `promotion_status` remains `NOT_PROMOTED`.

## Provider status

### Trading Economics

Best semantic benchmark. Existing adapter/mapping/canary remains available for public BYO-subscription use; it is not required for the maintainer's personal runtime.

### MetaTrader 5

Primary zero-cost machine canary. Service compiles with 0 errors, runs locally, exports valid calendar rows, and captures pre-release forecasts on the live Windows Work PC.

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

- MT5 forecast-to-survey-consensus equivalence still requires repeated cross-source evidence across multiple releases.
- Private consensus/surprise overlay contract and dashboard consumer path are not yet implemented.
- public snapshot intentionally has no third-party consensus/surprise values.
- dashboard embedded live fallback lags standalone collector coverage.
- dashboard legacy rolling-21-day smoke gate can false-fail.

## Exact next action

**After tonight's 20:30 Asia/Taipei CPI release, run official collector to record Actuals, verify Surprise calculation against MT5 pre-release provider_forecast, and continue accumulating pre-release canary samples.**
