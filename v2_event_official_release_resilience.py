from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from typing import Any

import v2_event_official as backend
import v2_event_official_us_phase2 as phase2
import v2_event_radar as core


CENSUS_ECON_WIDGET_URL = "https://www.census.gov/econwidget"
_BASE_RETAIL_METRICS = phase2._retail_metrics

_MONTH_HEADING = (
    r"January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan/Feb|Apr/May|Oct/Nov|Dec/Jan"
)
_RATE_TOKEN = r"(?:\d+(?:\.\d+)?(?:[-\s]\d+/\d+)?|\d+/\d+)"


def _year_fomc_section(text: str, year: int) -> str:
    plain = backend._plain_text(text)
    match = re.search(
        rf"\b{year}\s+FOMC Meetings\b(.*?)(?=\b20\d{{2}}\s+FOMC Meetings\b|$)",
        plain,
        re.I,
    )
    return match.group(1) if match else ""


def parse_fomc_meeting_days(text: str, year: int) -> list[date]:
    """Parse only regular meeting date ranges, never minutes-release dates.

    The Fed calendar also contains strings such as ``Released February 18, 2026``.
    The old flattened-text parser treated those single dates as new meetings.  A
    regular meeting row is represented by a month heading immediately followed by
    a day range (for example ``September 15-16*``), so this parser requires the
    range shape and thereby fails closed on release-note dates.
    """

    section = _year_fomc_section(text, year)
    if not section:
        return []

    result: list[date] = []
    pattern = re.compile(
        rf"\b({_MONTH_HEADING})\s+(\d{{1,2}})-(\d{{1,2}})\*?\b",
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
            # We record the policy-decision day: the final day of the meeting.
            meeting_day = date(end_year, end_month, end_day)
            date(year, start_month, start_day)  # validate the opening day as well
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
    """Return a normalized federal-funds target range from statement prose.

    Supports both decimal forms (``4.25 to 4.5``) and the Fed's mixed-fraction
    forms (``3-3/4 to 4``).
    """

    plain = backend._plain_text(text)
    match = re.search(
        rf"target range for the federal funds rate.{{0,220}}?(?:at|to)\s+"
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
    """Parse the first-party Census Economic Indicators retail card.

    The widget may expose values either as visible text or HTML input values, so
    the parser inspects a narrow raw-HTML block as well as its plain-text form.
    """

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
    pct_match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", plain)
    if not sales_match:
        sales_match = re.search(r"value=[\"']\s*\$?\s*([\d,.]+)\s*B\s*[\"']", block, re.I)
    if not pct_match:
        pct_match = re.search(r"value=[\"']\s*([+-]?\d+(?:\.\d+)?)\s*%\s*[\"']", block, re.I)

    values: dict[str, str] = {}
    if sales_match:
        values["sales_level"] = f"${float(sales_match.group(1).replace(',', '')):g}B"
    if pct_match:
        values["headline_mom"] = backend._pct(pct_match.group(1))
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

    cache_bust = re.sub(r"[^A-Za-z0-9_-]", "", str(refresh_token or ""))[-48:]
    widget_url = CENSUS_ECON_WIDGET_URL + (f"?_radar={cache_bust}" if cache_bust else "")
    widget_html = backend._fetch_text(widget_url, refresh_token)
    reference, values = parse_census_retail_widget(widget_html)
    if reference != expected or not values.get("headline_mom"):
        return base_metrics
    return _merge_retail_widget_metrics(base_metrics, values)


def install() -> None:
    # Runtime monkeypatches intentionally sit after the existing official-source
    # modules. The public snapshot contract does not change; only first-party
    # collection resilience is hardened.
    backend._us_fomc_events = _us_fomc_events_resilient
    backend._fed_target_result = _fed_target_result_resilient
    phase2._retail_metrics = _retail_metrics_resilient


install()
