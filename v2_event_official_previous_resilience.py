from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from functools import lru_cache
from io import BytesIO
import re
from urllib.request import Request, urlopen

from pypdf import PdfReader

import v2_event_official as backend
import v2_event_official_release_resilience as release_resilience
import v2_event_official_us_phase2 as phase2
import v2_event_radar as core


RETAIL_PDF_BASE = "https://www2.census.gov/retail/releases/historical/marts"
RETAIL_ADJUSTED_TOTAL_URL = "https://www.census.gov/retail/marts/www/adv44X72.txt"
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


def _parse_adjusted_total_series(text: str) -> dict[date, float]:
    """Parse only the adjusted Retail & Food Services level table.

    The Census text file contains a later ``SEASONAL FACTORS`` section with its
    own year-labelled rows. Stop before that section so factor rows can never
    overwrite the monthly sales levels collected above.
    """

    result: dict[date, float] = {}
    for line in str(text or "").splitlines():
        if "SEASONAL FACTORS" in line.upper():
            break
        match = re.match(r"^\s*(20\d{2})\s+(.+?)\s*$", line)
        if not match:
            continue
        year = int(match.group(1))
        values: list[float] = []
        for token in match.group(2).split():
            try:
                values.append(float(token.replace(",", "")))
            except ValueError:
                break
        if not values:
            continue
        for month, value in enumerate(values[:12], start=1):
            result[date(year, month, 1)] = value
    return result


def _retail_timeseries_previous(reference_month: date, refresh_token: str) -> str:
    """Derive the revised prior-month MoM from current official adjusted levels.

    This is a fallback for release-day windows where the Economic Indicators
    widget has updated but the archived release PDF has not propagated yet.
    """

    text = backend._fetch_text(RETAIL_ADJUSTED_TOTAL_URL, refresh_token)
    series = _parse_adjusted_total_series(text)
    previous_month = phase2._previous_month(reference_month)
    two_months_back = phase2._previous_month(previous_month)
    previous_level = series.get(previous_month)
    earlier_level = series.get(two_months_back)
    if previous_level is None or earlier_level in (None, 0):
        return ""
    change = (previous_level / earlier_level - 1.0) * 100.0
    return backend._pct(f"{change:.1f}")


def _merge_retail_previous(
    base_metrics: list[dict],
    values: dict[str, str],
    *,
    source_series: str = "Census MARTS release PDF",
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
            source_series=source_series,
        )
        result.append(primary)
        by_id["headline_mom"] = primary
    elif primary is not None:
        if actual and not primary.get("actual"):
            primary["actual"] = actual
        if previous:
            primary["previous"] = previous
        if actual or previous:
            primary["source_series"] = source_series
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
                source_series=source_series,
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

    # Preferred post-release source: the current release PDF, because its prose
    # explicitly carries the revised/unrevised prior-month change.
    pdf_values = _retail_pdf_values(reference)
    merged = _merge_retail_previous(base_metrics, pdf_values) if pdf_values else base_metrics
    primary = next((row for row in merged if row.get("is_primary")), None)
    if primary and primary.get("previous"):
        return merged

    # Release-day propagation can leave the archive PDF one step behind the
    # already-current widget. In that narrow case, derive Previous from Census'
    # current seasonally adjusted total series rather than using a stale initial
    # value from last month's snapshot.
    previous = _retail_timeseries_previous(reference, refresh_token)
    if not previous:
        return merged
    return _merge_retail_previous(
        merged,
        {"previous_mom": previous},
        source_series="Census MARTS adjusted total series",
    )


def clear_previous_value_caches() -> None:
    _fetch_retail_pdf_text.cache_clear()


def install() -> None:
    backend._us_fomc_events = _us_fomc_events_with_previous
    phase2._retail_metrics = _retail_metrics_with_previous


install()
