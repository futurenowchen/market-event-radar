# Consensus Provider Audit

Reconciled: 2026-09-11

## Current decision

Do **not** pay for Trading Economics for the current personal deployment. Keep Trading Economics as the semantic/reference benchmark because its documentation cleanly distinguishes survey `Forecast` from proprietary `TEForecast`, but move the active zero-cost canary to **MetaTrader 5 Economic Calendar**.

The zero-cost validation stack is:

1. **MetaTrader 5 / MQL5 Economic Calendar** — primary machine-readable canary candidate.
2. **Myfxbook Economic Calendar** — free human-readable/exportable cross-check because it labels a separate `Consensus` column.
3. Promote an MT5 forecast to canonical `consensus` only after same-release identity/unit/time checks and repeated cross-source agreement. Until then call it `provider_forecast`, not survey consensus.

The public official feed remains unchanged.

## Why MetaTrader 5 is the first zero-cost canary

MetaQuotes documents that MetaTrader 5 is free to download and includes fundamental analysis based on financial news and an Economic Calendar. Demo accounts can be opened without investment and provide the same platform functionality as live accounts for testing.

The built-in Economic Calendar exposes `actual`, `previous`, `revised previous`, and `forecast` values through the supported MQL5 interface. `CalendarValueHistory`, `CalendarValueHistoryByEvent`, `CalendarValueLast`, and related functions provide programmatic current/history access. MetaTrader help also states that the calendar shows current, forecast, and previous values and covers hundreds of macroeconomic indicators.

A recent MQL5-hosted technical article describes `forecast_value` as the value economists expected before release. That is promising, but the official structure/reference itself only guarantees a `forecast` field; it does not document the survey methodology with the same precision as Trading Economics. Therefore MT5 must pass our cross-source canary before its forecast is promoted to `ConsensusObservation.consensus`.

References:

- https://www.metatrader5.com/en/download
- https://www.metatrader5.com/en/terminal/help/startworking/acc_open
- https://www.metatrader5.com/en/terminal/help/charts_analysis/fundamental
- https://www.mql5.com/en/docs/constants/structures/mqlcalendar
- https://www.mql5.com/en/docs/calendar/calendarvaluehistory
- https://www.mql5.com/en/docs/calendar/calendarvaluelast
- https://www.mql5.com/en/articles/23546

### MT5 integration constraint

The supported Economic Calendar API lives inside MetaTrader/MQL5; the normal Python `MetaTrader5` package does not expose these calendar functions. The practical bridge is a small MQL5 Service/EA that exports only the required fields to a local/private JSON or CSV file for a Python worker to consume.

A recent free MQL5 Code Base project named `CalendarExport` demonstrates this bridge pattern, but any third-party code must be reviewed before reuse:

- https://www.mql5.com/en/code/76951

## Myfxbook status

Myfxbook's free Economic Calendar visibly separates `Previous`, `Consensus`, and `Actual`. Its help page says events include those fields and the calendar supports exporting the event list; the current UI offers CSV/XML export.

This makes Myfxbook useful as a **free validation source** for the MT5 canary. However, the official Myfxbook API documentation reviewed is oriented to a user's account data and does not document a supported Economic Calendar API. Do not build unattended production ingestion around undocumented/internal calendar endpoints.

References:

- https://www.myfxbook.com/forex-economic-calendar
- https://www.myfxbook.com/help/knowledge-base/economic-calendar/
- https://www.myfxbook.com/api

## Trading Economics status

Trading Economics remains the cleanest semantic benchmark because its documentation distinguishes:

- `Actual`: observed release value
- `Previous`: previous release value
- `Forecast`: consensus forecast from a representative group of economists
- `TEForecast`: Trading Economics' own projection

It also documents point-in-time calendar access. The existing TE adapter, conservative mapping registry, and canary remain useful reference code, but a paid TE subscription is not justified for the current personal deployment.

References:

- https://docs.tradingeconomics.com/economic_calendar/schema/
- https://docs.tradingeconomics.com/economic_calendar/snapshot/
- https://docs.tradingeconomics.com/economic_calendar/point-in-time/

## Excluded / lower-priority alternatives

### Forex Factory — exclude for automated persistence

Forex Factory offers calendar exports, but its Notices explicitly prohibit copying, republication, or redistribution of its calendar/FEED compilation without prior written consent. Do not use it as an automated persisted or public source.

Reference:

- https://www.forexfactory.com/news/notices

### Finnhub — not free for this layer

Finnhub documents Economic Calendar as `Premium Access Required`; historical events/surprises are Enterprise. Exclude from the zero-cost path.

Reference:

- https://finnhub.io/docs/api/calendar-economic

### EODHD — endpoint exists, free-plan fit not established

EODHD documents an Economic Events endpoint with `actual`, `previous`, and `estimate`. Its Free Starter plan is $0 with 20 calls/day, but the free-plan description is limited to EOD/splits/dividends and limited market data; Economic Events entitlement on the free tier is not established by the reviewed plan documentation. The `estimate` field is also described as an estimated/forecast value, not explicitly as survey consensus. Do not promote it to canonical consensus without both entitlement and provenance proof.

References:

- https://eodhd.com/financial-apis/economic-events-data-api
- https://eodhd.com/

### Financial Modeling Prep — canary-only secondary candidate

FMP has a current Economic Calendar endpoint in its stable API family and a free account tier exists, but the reviewed official material did not establish that the free tier is entitled to this endpoint or that its `estimate` semantics equal survey consensus. It can be probed later with a free key, but it is lower priority than MT5.

## Licensing / persistence boundary

Do not assume that free viewing or free terminal access grants unrestricted redistribution rights.

For the personal system, keep the architecture conservative:

- public `market-event-radar`: official-source snapshot, open-source provider adapters/mapping/surprise logic, **no persisted third-party consensus values unless redistribution is explicitly permitted**;
- private runtime/overlay: fetch or export third-party forecast/consensus values for personal use, preserve provider provenance and pre-release capture time, and compute Surprise with the public library code;
- private `investment-dashboard`: consume the official public snapshot plus the private consensus/surprise overlay.

This preserves the existing ownership boundary at the code/logic level while avoiding publication of vendor-compiled values.

## Existing Trading Economics mapping baseline

The code registry `market_event_radar/consensus_mapping.py` remains intentionally conservative. Current TE mappings cover CPI, headline PPI, PCE, Employment Situation, Initial Claims, Retail Sales, and ECI. Core PPI remains deliberately unmapped because the official BLS series used by this radar excludes food, energy, **and trade services**, while the common provider Core PPI concept is not semantically identical.

The governing rule remains: **semantic equivalence beats coverage**.

## Hard rules

1. Provider credentials, if any, are secret-only.
2. Missing consensus data must never degrade the official feed.
3. Only a forecast/consensus captured before the official release cutoff may drive original Surprise.
4. Preserve provider id, provider event/value id, event/metric identity, fetch/capture time, release time, raw value, and unit.
5. Do not mutate official `Actual` / `Previous` provenance.
6. Do not call a generic forecast `consensus` until its provenance/behavior is validated.
7. Do not publicly persist vendor-compiled values unless redistribution rights are clear.
8. A provider mapping must have an explicit Surprise semantic rule before use.

## Exact next provider work

Build an isolated **MT5 Economic Calendar canary/export bridge** that emits private/local JSON only. Capture forecast values *before* release for a small high-signal set (CPI/PPI/Claims first), then compare event identity, units, timestamps, and values against Myfxbook's explicitly labeled Consensus. Do not modify the public production snapshot during this canary.