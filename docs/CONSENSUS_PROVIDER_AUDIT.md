# Consensus Provider Audit

Reconciled: 2026-09-11

## Decision

Use **Trading Economics** as the first consensus integration target, behind an optional provider interface.

## Why Trading Economics is eligible

Official documentation distinguishes four fields:

- `Actual`: observed release value
- `Previous`: previous release value
- `Forecast`: **consensus forecast from a representative group of economists**
- `TEForecast`: Trading Economics' own projection

This distinction is critical. The radar must use `Forecast` for market consensus and must never substitute `TEForecast`.

Trading Economics also documents point-in-time economic-calendar access that preserves how events appeared at a historical point, which is suitable for avoiding look-ahead bias and preserving pre-release consensus.

References:

- https://docs.tradingeconomics.com/economic_calendar/schema/
- https://docs.tradingeconomics.com/economic_calendar/snapshot/
- https://docs.tradingeconomics.com/economic_calendar/point-in-time/

## EODHD status

EODHD's Economic Events API documents `actual`, `previous`, and `estimate`. It is a viable secondary source candidate, but the public documentation reviewed does not define `estimate` with the same explicit survey-consensus provenance as Trading Economics. Do not label it canonical `consensus` until provenance/terms are confirmed.

Reference:

- https://eodhd.com/financial-apis/economic-events-data-api

## Verified Trading Economics identity mapping v1

The code registry is `market_event_radar/consensus_mapping.py`. It is intentionally conservative: an internal metric is mapped only when the TE indicator represents the same economic concept.

Current mapped families include:

- CPI: headline YoY/MoM and core YoY/MoM
- PPI: headline YoY/MoM only
- PCE: headline YoY/MoM and core YoY/MoM
- Employment Situation: Non Farm Payrolls, Unemployment Rate, Average Hourly Earnings MoM/YoY
- Initial Claims
- Retail Sales MoM/YoY
- Employment Cost Index total compensation QoQ

Public TE calendar/indicator pages reviewed for these identities expose names such as `Inflation Rate YoY`, `Inflation Rate MoM`, `Core Inflation Rate YoY`, `Core Inflation Rate MoM`, `Producer Prices Change`, `Producer Price Inflation MoM`, `PCE Price Index YoY`, `PCE Price Index MoM`, `Core PCE Price Index YoY`, `Core PCE Price Index MoM`, `Non Farm Payrolls`, `Unemployment Rate`, `Average Hourly Earnings MoM`, `Average Hourly Earnings YoY`, `Initial Jobless Claims`, `Retail Sales MoM`, `Retail Sales YoY`, and `Employment Cost Index`.

### Deliberate non-mapping: core PPI

Our official core PPI release bundle uses BLS series excluding **food, energy, and trade services**. Trading Economics' common `Core PPI` pages describe a core measure excluding **food and energy**. Those are not the same series. Therefore `ppi/core_yoy` and `ppi/core_mom` are intentionally unmapped in v1 instead of generating a misleading surprise comparison.

This is the governing mapping rule: semantic equivalence beats coverage.

## Integration constraints

1. Provider credentials are optional and secret-only.
2. Missing provider credentials return no consensus observations, not an error in the official feed.
3. Only a consensus captured before the official release cutoff is eligible for surprise computation.
4. Preserve provider id, provider event id/ticker, fetch time, point-in-time/as-of time, raw consensus, and source URL.
5. Do not mutate official `Actual` / `Previous` provenance.
6. Do not write provider model forecasts into the consensus field.
7. A provider mapping must also have an explicit surprise semantic rule before it can be used.

## Next provider work

Run a credentialed, non-production canary against the mapping registry. Verify returned TE rows, release-time alignment, units, metric identity, and pre-release `Forecast` availability. Persist the observed provider identifiers/matching evidence before any production snapshot enrichment.
