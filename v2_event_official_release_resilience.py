from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from typing import Any

import v2_event_official as backend
import v2_event_official_us_phase2 as phase2
import v2_event_radar as core


CENSUS_ECON_WIDGET_URL = "https://www.census.gov/econwidget"
RESULT_LOOKBACK = timedelta(hours=48)
_BASE_RETAIL_METRICS = phase2._retail_metrics

_MONTH_HEADING = (
    r"January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan/Feb|Apr/May|Oct/Nov|Dec/Jan"
)
_RATE_TOKEN = r"(?:\d+(?:\.\d+)?(?:[-–—\s]\d+/\d+)?|\d+/\d+)"


def _year_fomc_section(text: str, year: int) -> str:
    plain = backend._plain_text(text)
    match = re.search(
        rf"\b{year}\s+FOMC Meetings\b(.*?)(?=\b20\d{{2}}\s+FOMC Meetings\b|$)",
        plain,
        re.I,
    )
    return match.group(1) if match else ""


def parse_fomc_meeting_days(text: str, year: int) -> list[date]:
    """Parse only regular meeting ranges, never minutes-release dates."""

    section = _year_fomc_section(text, year)
    if not section:
        return []

    result: list[date] = []
    pattern = re.compile(
        rf"\b({_MONTH_HEADING})\s+(\d{{1,2}})\s*[-–—]\s*(\d{{1,2}})\*?\b",
        re.I,
    )
    for match in pattern.finditer(section):
        heading = match.group(1)
        start_day = int(match.group(2))
        end_day = int(match.group(3))
        month_parts = heading.split("/")
        start_month = backend._month_number(month_parts[0])
        end_month = backend._month_number(month_parts[-1])
        if start_month is None or end_month is None:
            continue
        end_year = year + (1 if end_month < start_month else 0)
        try:
            date(year, start_month, start_day)
            meeting_day = date(end_year, end_month, end_day)
        except ValueError:
            continue
        result.append(meeting_day)
    return sorted(set(result))


def _parse_rate_token(token: str) -> float | None:
    normalized = (
        str(token or "")
        .strip()
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
    )
    mixed = re.fullmatch(r"(\d+)(?:-|\s+)(\d+)/(\d+)", normalized)
    if mixed:
        denominator = int(mixed.group(3))
        if denominator == 0:
            return None
        return int(mixed.group(1)) + int(mixed.group(2)) / denominator
    fraction = re.fullmatch(r"(\d+)/(\d+)", normalized)
    if fraction:
        denominator = int(fraction.group(2))
        if denominator == 0:
            return None
        return int(fraction.group(1)) / denominator
    try:
        return float(normalized)
    except ValueError:
        return None


def _fmt_rate(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def parse_fed_target_range(text: str) -> str:
    """Normalize decimal or mixed-fraction federal-funds target ranges."""

    plain = backend._plain_text(text)
    match = re.search(
        rf"target range for the federal funds rate.{{0,260}}?(?:at|to)\s+"
        rf"({_RATE_TOKEN})\s+to\s+({_RATE_TOKEN})\s+percent",
        plain,
        re.I,
    )
    if not match:
        return ""
    low = _parse_rate_token(match.group(1))
    high = _parse_rate_token(match.group(2))
    if low is None or high is None or low > high:
        return ""
    return f"{_fmt_rate(low)}–{_fmt_rate(high)}%"


def _fed_target_result_resilient(meeting_day: date, refresh_token: str) -> tuple[str, str]:
    url = f"{backend.FED_PRESS_BASE}{meeting_day:%Y%m%d}a.htm"
    text = backend._fetch_text(url, refresh_token)
    actual = parse_fed_target_range(text)
    return (actual, "") if actual else ("", "")


def _us_fomc_events_resilient(
    start: datetime,
    end: datetime,
    refresh_token: str,
) -> tuple[list[core.MarketEvent], bool]:
    html = backend._fetch_text(backend.FED_FOMC_URL, refresh_token)
    if not html:
        return [], False

    events: list[core.MarketEvent] = []
    parsed_calendar = False
    now = datetime.now(backend.TPE)
    for year in sorted({start.year, end.year}):
        meeting_days = parse_fomc_meeting_days(html, year)
        parsed_calendar = parsed_calendar or bool(meeting_days)
        for meeting_day in meeting_days:
            dt = backend._dt_local(meeting_day, 14, 0, backend.NY)
            if not backend._in_window(dt, start, end):
                continue
            actual, previous = (
                _fed_target_result_resilient(meeting_day, refresh_token)
                if now >= dt + timedelta(minutes=5)
                else ("", "")
            )
            events.append(
                backend._event(
                    event_id=f"official-us-fed-fomc-{meeting_day.isoformat()}",
                    dt=dt,
                    title="美國聯邦公開市場委員會（FOMC）利率決議",
                    country="美國",
                    tier="S",
                    tags=("美國", "FOMC", "Fed", "利率", "全球風險資產"),
                    source="Federal Reserve",
                    source_url=backend.FED_FOMC_URL,
                    provider="official-us-fed-fomc",
                    actual=actual,
                    previous=previous,
                    category="央行事件",
                )
            )
    return core._dedupe(events), parsed_calendar


def parse_census_retail_widget(html: str) -> tuple[date | None, dict[str, str]]:
    """Parse the first-party Census Economic Indicators retail card."""

    raw = str(html or "")
    marker = re.search(r"Advance Monthly Retail Sales", raw, re.I)
    if not marker:
        return None, {}
    block = raw[marker.start() : marker.start() + 7000]
    plain = backend._plain_text(block)

    ref_match = re.search(
        r"([A-Za-z]+)\s+(20\d{2})\s+Report Released\s+"
        r"[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,\s+20\d{2}",
        plain,
        re.I,
    )
    if not ref_match:
        ref_match = re.search(r"([A-Za-z]+)\s+(20\d{2})\s+Report Released", block, re.I)
    if not ref_match:
        return None, {}
    month = phase2._MONTHS.get(ref_match.group(1).lower().rstrip("."))
    if month is None:
        return None, {}
    reference = date(int(ref_match.group(2)), month, 1)

    sales_match = re.search(r"\$\s*([\d,.]+)\s*B\b", plain, re.I)
    pct_match = re.search(r"([+-]?)\s*(\d+(?:\.\d+)?)\s*%", plain)
    if not sales_match:
        sales_match = re.search(r"value=[\"']\s*\$?\s*([\d,.]+)\s*B\s*[\"']", block, re.I)
    if not pct_match:
        pct_match = re.search(r"value=[\"']\s*([+-]?)\s*(\d+(?:\.\d+)?)\s*%\s*[\"']", block, re.I)

    values: dict[str, str] = {}
    if sales_match:
        values["sales_level"] = f"${float(sales_match.group(1).replace(',', '')):g}B"
    if pct_match:
        signed = f"{pct_match.group(1)}{pct_match.group(2)}"
        values["headline_mom"] = backend._pct(signed)
    return reference, values


def _merge_retail_widget_metrics(
    base_metrics: list[dict[str, Any]],
    widget_values: dict[str, str],
) -> list[dict[str, Any]]:
    result = [dict(row) for row in base_metrics]
    by_id = {str(row.get("metric_id") or ""): row for row in result}

    specs = (
        ("headline_mom", "零售與餐飲銷售 MoM", "%", True),
        ("sales_level", "零售與餐飲銷售額", "USD billions", False),
    )
    for metric_id, label, unit, primary in specs:
        actual = str(widget_values.get(metric_id) or "").strip()
        if not actual:
            continue
        existing = by_id.get(metric_id)
        if existing is not None:
            existing["actual"] = actual
            existing["source_series"] = "Census Economic Indicators / MARTS"
            if primary:
                existing["is_primary"] = True
            continue
        row = phase2._metric(
            metric_id,
            label,
            actual=actual,
            unit=unit,
            is_primary=primary,
            source_series="Census Economic Indicators / MARTS",
        )
        result.append(row)
        by_id[metric_id] = row
    return result


def _retail_metrics_resilient(
    event: core.MarketEvent,
    now: datetime,
    refresh_token: str,
) -> list[dict[str, Any]]:
    base_metrics = _BASE_RETAIL_METRICS(event, now, refresh_token)
    if now < event.time_tpe:
        return base_metrics
    if any(row.get("is_primary") and row.get("actual") for row in base_metrics):
        return base_metrics

    expected = getattr(event, "reference_month", None)
    if not isinstance(expected, date):
        return base_metrics

    # _fetch_text already includes refresh_token in its cache key, so a query-string
    # cache buster is unnecessary and can cause Census edge/CDN variants to return a
    # different representation. Keep the canonical first-party widget URL stable.
    widget_html = backend._fetch_text(CENSUS_ECON_WIDGET_URL, refresh_token)
    reference, values = parse_census_retail_widget(widget_html)
    if reference != expected or not values.get("headline_mom"):
        return base_metrics
    return _merge_retail_widget_metrics(base_metrics, values)


def _load_event_radar_resilient(days: int = 7) -> core.RadarEvents:
    now = datetime.now(backend.TPE)
    start = now - RESULT_LOOKBACK
    end = now + timedelta(days=days)
    daily_token = f"official-daily-{now.date().isoformat()}"
    macro, health = backend.collect_official_macro(start, end, daily_token)
    companies = backend._company_events(start, end, daily_token)
    raw = core._dedupe([*macro, *companies])
    radar = core.RadarEvents(core._homepage_events(raw, days), raw)
    radar.source_health = health
    radar.official_macro_ready = backend._official_macro_ready(macro, health)
    return radar


def _smart_refresh_missing_resilient(
    events: list[core.MarketEvent],
    now: datetime | None = None,
) -> list[core.MarketEvent]:
    now = now or datetime.now(backend.TPE)
    due = [
        event
        for event in events
        if event.expects_result
        and not event.actual
        and now >= event.time_tpe + timedelta(minutes=5)
        and now - event.time_tpe <= RESULT_LOOKBACK
    ]
    if not due:
        return events

    token = f"official-smart-{now:%Y%m%d-%H%M}"
    start = now - RESULT_LOOKBACK
    end = now + timedelta(days=1)
    refreshed: list[core.MarketEvent] = []
    if any(event.provider.startswith("official-") for event in due):
        macro, _ = backend.collect_official_macro(start, end, token)
        refreshed.extend(macro)

    symbols = {event.symbol for event in due if event.provider == "yfinance" and event.symbol}
    profiles = {profile.ticker: profile for profile in core.AI_COMPANIES}
    for symbol in symbols:
        profile = profiles.get(symbol)
        if profile:
            refreshed.extend(core._company_events(profile, token))
    return core._dedupe([*events, *refreshed]) if refreshed else events


def install() -> None:
    backend._us_fomc_events = _us_fomc_events_resilient
    backend._fed_target_result = _fed_target_result_resilient
    phase2._retail_metrics = _retail_metrics_resilient
    backend.load_event_radar = _load_event_radar_resilient
    backend.smart_refresh_missing = _smart_refresh_missing_resilient
    backend.load_event_radar.clear = backend.clear_event_caches


install()
