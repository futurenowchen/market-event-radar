from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

import v2_event_official as backend
import v2_event_radar as core
import v2_event_release_metrics as release_metrics

PPI_SCHEDULE_URL = "https://www.bls.gov/schedule/news_release/ppi.htm"

# Published 2026 BLS PPI calendar. The live first-party schedule remains primary;
# this safety copy is used only when a GitHub-hosted runner cannot read the page.
PPI_2026 = (
    date(2026, 1, 14), date(2026, 1, 30), date(2026, 2, 27), date(2026, 3, 18),
    date(2026, 4, 14), date(2026, 5, 13), date(2026, 6, 11), date(2026, 7, 15),
    date(2026, 8, 13), date(2026, 9, 10), date(2026, 10, 15), date(2026, 11, 13),
    date(2026, 12, 15),
)

_BASE_US_BLS_EVENTS = backend._us_bls_events
_BASE_US_BEA_SCHEDULE = backend._us_bea_schedule


def _parse_release_day(value: str) -> date | None:
    text = " ".join(value.replace("Sept.", "Sep").replace("Sep.", "Sep").split())
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _ppi_days(refresh_token: str) -> tuple[list[date], bool]:
    html = backend._fetch_text(PPI_SCHEDULE_URL, refresh_token)
    if not html:
        return list(PPI_2026), False
    days: list[date] = []
    for row in backend._table_rows(html):
        if len(row) < 2:
            continue
        day = _parse_release_day(row[1])
        if day is not None:
            days.append(day)
    if not days:
        return list(PPI_2026), False
    return sorted(set(days)), True


def _with_metrics(event: core.MarketEvent, metrics: list[dict]) -> core.MarketEvent:
    primary = next((row for row in metrics if row.get("is_primary")), None)
    actual = str((primary or {}).get("actual") or event.actual)
    previous = str((primary or {}).get("previous") or event.previous)
    status = "released" if actual else event.status
    enriched = replace(event, actual=actual, previous=previous, status=status)
    # MarketEvent deliberately remains schema-v2 compatible. `metrics` is an
    # optional extension carried by the snapshot serializer and ignored by old
    # consumers, so adding richer release data cannot break the legacy API.
    object.__setattr__(enriched, "metrics", tuple(dict(row) for row in metrics))
    return enriched


def _enrich_bls_event(event: core.MarketEvent, now: datetime, refresh_token: str) -> core.MarketEvent:
    family = ""
    if event.provider == "official-us-bls-cpi":
        family = "cpi"
    elif event.provider == "official-us-bls-nfp":
        family = "nfp"
    if not family:
        return event
    metrics = release_metrics.metrics_for_event(event, now, refresh_token)
    return _with_metrics(event, metrics) if metrics else event


def _ppi_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    days, live_ok = _ppi_days(refresh_token)
    now = datetime.now(backend.TPE)
    events: list[core.MarketEvent] = []
    for release_day in days:
        dt = backend._dt_local(release_day, 8, 30, backend.NY)
        if not backend._in_window(dt, start, end):
            continue
        event = backend._event(
            event_id=f"official-us-bls-ppi-{release_day.isoformat()}",
            dt=dt,
            title="美國生產者物價指數（PPI）",
            country="美國",
            tier="S",
            tags=("美國", "PPI", "通膨", "Fed", "NASDAQ", "台指"),
            source="U.S. Bureau of Labor Statistics (BLS)",
            source_url=PPI_SCHEDULE_URL,
            provider="official-us-bls-ppi",
        )
        metrics = release_metrics.metrics_for_event(event, now, refresh_token)
        events.append(_with_metrics(event, metrics) if metrics else event)
    return events, bool(live_ok or PPI_2026)


def _us_bls_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    base_events, base_ok = _BASE_US_BLS_EVENTS(start, end, refresh_token)
    now = datetime.now(backend.TPE)
    enriched = [_enrich_bls_event(event, now, refresh_token) for event in base_events]
    ppi_events, ppi_ok = _ppi_events(start, end, refresh_token)
    return core._dedupe([*enriched, *ppi_events]), bool(base_ok or ppi_ok)


def _us_bea_schedule(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    events, ok = _BASE_US_BEA_SCHEDULE(start, end, refresh_token)
    now = datetime.now(backend.TPE)
    result: list[core.MarketEvent] = []
    for event in events:
        if event.provider != "official-us-bea-pce":
            result.append(event)
            continue
        metrics = release_metrics.metrics_for_event(event, now, refresh_token)
        result.append(_with_metrics(event, metrics) if metrics else event)
    return result, ok


def install() -> None:
    backend._us_bls_events = _us_bls_events
    backend._us_bea_schedule = _us_bea_schedule


install()
