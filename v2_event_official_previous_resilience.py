from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from functools import lru_cache
from io import BytesIO
from urllib.request import Request, urlopen

from pypdf import PdfReader

import v2_event_official as backend
import v2_event_official_release_resilience as release_resilience
import v2_event_official_us_phase2 as phase2
import v2_event_radar as core


RETAIL_PDF_BASE = "https://www2.census.gov/retail/releases/historical/marts"
_BASE_FOMC_EVENTS = backend._us_fomc_events
_BASE_RETAIL_METRICS = phase2._retail_metrics


def _previous_fomc_meeting_day(calendar_text: str, meeting_day: date) -> date | None:
    days: list[date] = []
    for year in (meeting_day.year - 1, meeting_day.year):
        days.extend(release_resilience.parse_fomc_meeting_days(calendar_text, year))
    previous = [day for day in days if day < meeting_day]
    return max(previous) if previous else None


def _fomc_target_for_day(meeting_day: date, refresh_token: str) -> str:
    url = f"{backend.FED_PRESS_BASE}{meeting_day:%Y%m%d}a.htm"
    statement = backend._fetch_text(url, refresh_token)
    return release_resilience.parse_fed_target_range(statement)


def _us_fomc_events_with_previous(
    start: datetime,
    end: datetime,
    refresh_token: str,
) -> tuple[list[core.MarketEvent], bool]:
    events, ok = _BASE_FOMC_EVENTS(start, end, refresh_token)
    if not events:
        return events, ok

    calendar = backend._fetch_text(backend.FED_FOMC_URL, refresh_token)
    if not calendar:
        return events, ok

    enriched: list[core.MarketEvent] = []
    for event in events:
        if event.previous:
            enriched.append(event)
            continue
        meeting_day = event.time_tpe.astimezone(backend.NY).date()
        previous_day = _previous_fomc_meeting_day(calendar, meeting_day)
        previous = _fomc_target_for_day(previous_day, refresh_token) if previous_day else ""
        enriched.append(replace(event, previous=previous) if previous else event)
    return core._dedupe(enriched), ok


@lru_cache(maxsize=24)
def _fetch_retail_pdf_text(reference_month: date) -> str:
    url = f"{RETAIL_PDF_BASE}/adv{reference_month:%y%m}.pdf"
    request = Request(
        url,
        headers={"User-Agent": backend.USER_AGENT, "Accept": "application/pdf,*/*"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read()
        reader = PdfReader(BytesIO(raw))
        return " ".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


def _retail_pdf_values(reference_month: date) -> dict[str, str]:
    text = " ".join(_fetch_retail_pdf_text(reference_month).split())
    reference, values = phase2._parse_retail_release_text(text)
    return values if reference == reference_month else {}


def _merge_retail_previous(
    base_metrics: list[dict],
    values: dict[str, str],
) -> list[dict]:
    result = [dict(row) for row in base_metrics]
    by_id = {str(row.get("metric_id") or ""): row for row in result}

    actual = str(values.get("headline_mom") or "")
    previous = str(values.get("previous_mom") or "")
    primary = by_id.get("headline_mom")
    if primary is None and (actual or previous):
        primary = phase2._metric(
            "headline_mom",
            "零售與餐飲銷售 MoM",
            actual=actual,
            previous=previous,
            unit="%",
            is_primary=True,
            source_series="Census MARTS release PDF",
        )
        result.append(primary)
        by_id["headline_mom"] = primary
    elif primary is not None:
        if actual and not primary.get("actual"):
            primary["actual"] = actual
        if previous:
            primary["previous"] = previous
        primary["source_series"] = "Census MARTS release PDF"
        primary["is_primary"] = True

    additions = (
        ("headline_yoy", "零售與餐飲銷售 YoY", "%"),
        ("sales_level", "零售與餐飲銷售額", "USD billions"),
    )
    for metric_id, label, unit in additions:
        value = str(values.get(metric_id) or "")
        if not value:
            continue
        row = by_id.get(metric_id)
        if row is None:
            row = phase2._metric(
                metric_id,
                label,
                actual=value,
                unit=unit,
                source_series="Census MARTS release PDF",
            )
            result.append(row)
            by_id[metric_id] = row
        elif not row.get("actual"):
            row["actual"] = value
    return result


def _retail_metrics_with_previous(
    event: core.MarketEvent,
    now: datetime,
    refresh_token: str,
) -> list[dict]:
    base_metrics = _BASE_RETAIL_METRICS(event, now, refresh_token)
    primary = next((row for row in base_metrics if row.get("is_primary")), None)
    if primary and primary.get("previous"):
        return base_metrics

    reference = getattr(event, "reference_month", None)
    if not isinstance(reference, date) or now < event.time_tpe:
        return base_metrics

    values = _retail_pdf_values(reference)
    if not values:
        return base_metrics
    return _merge_retail_previous(base_metrics, values)


def clear_previous_value_caches() -> None:
    _fetch_retail_pdf_text.cache_clear()


def install() -> None:
    backend._us_fomc_events = _us_fomc_events_with_previous
    phase2._retail_metrics = _retail_metrics_with_previous


install()
