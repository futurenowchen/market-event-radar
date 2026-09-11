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

## Integration constraints

1. Provider credentials are optional and secret-only.
2. Missing provider credentials return no consensus observations, not an error in the official feed.
3. Only a consensus captured before the official release cutoff is eligible for surprise computation.
4. Preserve provider id, provider event id/ticker, fetch time, point-in-time/as-of time, raw consensus, and source URL.
5. Do not mutate official `Actual` / `Previous` provenance.
6. Do not write provider model forecasts into the consensus field.

## Next provider work

After the provider-neutral contract is green, add deterministic mapping from internal high-signal event/metric identities to Trading Economics calendar event/ticker identities, then run a credentialed canary before enriching production snapshots.
