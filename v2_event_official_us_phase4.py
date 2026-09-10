from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any, Iterable

import v2_event_official as backend
import v2_event_official_us_phase3  # noqa: F401  # install Phases 1-3 before wrapping
import v2_event_official_us_phase2 as phase2
import v2_event_radar as core


ISM_CALENDAR_URL = "https://www.ismworld.org/supply-management-news-and-reports/reports/rob-report-calendar/"
BLS_PRODUCTIVITY_SCHEDULE_URL = "https://www.bls.gov/schedule/news_release/prod2.htm"
FED_CALENDAR_BASE = "https://www.federalreserve.gov/newsevents"

PRODUCTIVITY_SERIES = {
    "labor_productivity": "PRS85006092",
    "unit_labor_costs": "PRS85006112",
}

# First-party calendars remain primary. These 2026 anchors are deterministic
# fallbacks so a transient source outage does not erase a known event window.
ISM_2026 = (
    (date(2026, 1, 5), "manufacturing"), (date(2026, 1, 7), "services"),
    (date(2026, 2, 2), "manufacturing"), (date(2026, 2, 4), "services"),
    (date(2026, 3, 2), "manufacturing"), (date(2026, 3, 4), "services"),
    (date(2026, 4, 1), "manufacturing"), (date(2026, 4, 6), "services"),
    (date(2026, 5, 1), "manufacturing"), (date(2026, 5, 5), "services"),
    (date(2026, 6, 1), "manufacturing"), (date(2026, 6, 3), "services"),
    (date(2026, 7, 1), "manufacturing"), (date(2026, 7, 6), "services"),
    (date(2026, 8, 3), "manufacturing"), (date(2026, 8, 5), "services"),
    (date(2026, 9, 1), "manufacturing"), (date(2026, 9, 3), "services"),
    (date(2026, 10, 1), "manufacturing"), (date(2026, 10, 5), "services"),
    (date(2026, 11, 2), "manufacturing"), (date(2026, 11, 4), "services"),
    (date(2026, 12, 1), "manufacturing"), (date(2026, 12, 3), "services"),
)

PRODUCTIVITY_2026 = (
    ((2025, 3), date(2026, 1, 8)),
    ((2025, 4), date(2026, 3, 5)),
    ((2026, 1), date(2026, 5, 7)),
    ((2026, 2), date(2026, 8, 6)),
    ((2026, 3), date(2026, 11, 5)),
)

_BASE_US_BLS_EVENTS = backend._us_bls_events
_BASE_US_BEA_SCHEDULE = backend._us_bea_schedule
_BASE_US_FOMC_EVENTS = backend._us_fomc_events
_BASE_COLLECT_OFFICIAL_MACRO = backend.collect_official_macro

_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
_MONTH_NAMES = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)


def _metric(
    metric_id: str,
    label: str,
    *,
    actual: str = "",
    previous: str = "",
    unit: str = "",
    is_primary: bool = False,
    source_series: str = "",
) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "label": label,
        "actual": actual,
        "forecast": "",
        "previous": previous,
        "unit": unit,
        "is_primary": bool(is_primary),
        "source_series": source_series,
    }


def _with_metrics(event: core.MarketEvent, metrics: list[dict[str, Any]]) -> core.MarketEvent:
    primary = next((row for row in metrics if row.get("is_primary")), None)
    actual = str((primary or {}).get("actual") or event.actual)
    previous = str((primary or {}).get("previous") or event.previous)
    enriched = replace(event, actual=actual, previous=previous, status="released" if actual else event.status)
    if metrics:
        object.__setattr__(enriched, "metrics", tuple(dict(row) for row in metrics))
    return enriched


def _with_tags(event: core.MarketEvent, *tags: str) -> core.MarketEvent:
    merged = tuple(dict.fromkeys((*event.market_tags, *(tag for tag in tags if tag))))
    return replace(event, market_tags=merged)


def _parse_release_day(value: str) -> date | None:
    text = " ".join(str(value or "").replace("Sept.", "Sep").replace("Sep.", "Sep").split())
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_reference_quarter(value: str) -> tuple[int, int] | None:
    text = " ".join(str(value or "").split()).lower()
    year_match = re.search(r"(20\d{2})", text)
    if not year_match:
        return None
    for word, quarter in (("first", 1), ("second", 2), ("third", 3), ("fourth", 4)):
        if word in text:
            return int(year_match.group(1)), quarter
    numeric = re.search(r"\b([1-4])(?:st|nd|rd|th)?\s+quarter\b", text)
    if numeric:
        return int(year_match.group(1)), int(numeric.group(1))
    return None


def _previous_quarter(value: tuple[int, int]) -> tuple[int, int]:
    year, quarter = value
    return (year - 1, 4) if quarter == 1 else (year, quarter - 1)


def _parse_ism_schedule_rows(rows: Iterable[list[str]], year: int = 2026) -> list[tuple[date, str]]:
    result: list[tuple[date, str]] = []
    for row in rows:
        if len(row) < 3:
            continue
        joined = " | ".join(row)
        month_match = re.search(r"([A-Za-z]+)\s+(20\d{2})", joined)
        if not month_match or int(month_match.group(2)) != year:
            continue
        month = _MONTHS.get(month_match.group(1).lower().rstrip("."))
        if month is None:
            continue
        day_values: list[int] = []
        for cell in row[1:]:
            match = re.search(r"\b([0-3]?\d)\b", str(cell))
            if not match:
                continue
            day = int(match.group(1))
            if 1 <= day <= 31:
                day_values.append(day)
        if len(day_values) < 2:
            continue
        for family, day in (("manufacturing", day_values[0]), ("services", day_values[1])):
            try:
                result.append((date(year, month, day), family))
            except ValueError:
                pass
    return sorted(set(result))


def _ism_schedule(refresh_token: str) -> tuple[list[tuple[date, str]], bool]:
    html = backend._fetch_text(ISM_CALENDAR_URL, refresh_token)
    rows = _parse_ism_schedule_rows(backend._table_rows(html), 2026) if html else []
    return (rows if rows else list(ISM_2026), bool(rows))


def _ism_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    schedule, live_ok = _ism_schedule(refresh_token)
    events: list[core.MarketEvent] = []
    for release_day, family in schedule:
        dt = backend._dt_local(release_day, 10, 0, backend.NY)
        if not backend._in_window(dt, start, end):
            continue
        manufacturing = family == "manufacturing"
        events.append(
            backend._event(
                event_id=f"official-us-ism-{family}-{release_day.isoformat()}",
                dt=dt,
                title="美國ISM製造業PMI" if manufacturing else "美國ISM服務業PMI",
                country="美國",
                tier="A",
                tags=(
                    "美國", "ISM", "PMI", "製造業" if manufacturing else "服務業",
                    "景氣", "Fed", "schedule-only", "未接授權數值",
                ),
                source="Institute for Supply Management (ISM)",
                source_url=ISM_CALENDAR_URL,
                provider=f"official-us-ism-{family}",
                category="總體經濟",
                importance=2,
                expects_result=False,
            )
        )
    return events, bool(live_ok or ISM_2026)


def _productivity_schedule(refresh_token: str) -> tuple[list[tuple[tuple[int, int], date]], bool]:
    html = backend._fetch_text(BLS_PRODUCTIVITY_SCHEDULE_URL, refresh_token)
    rows: list[tuple[tuple[int, int], date]] = []
    if html:
        for row in backend._table_rows(html):
            if len(row) < 2:
                continue
            # Only preliminary/initial releases enter the radar. Revisions stay
            # out of the event universe to avoid turning this into a full calendar.
            reference_text = row[0]
            if "(P)" not in reference_text.upper():
                continue
            reference = _parse_reference_quarter(reference_text)
            release_day = _parse_release_day(row[1])
            if reference and release_day:
                rows.append((reference, release_day))
    return (sorted(set(rows)) if rows else list(PRODUCTIVITY_2026), bool(rows))


def _quarter_value(
    data: dict[str, list[tuple[tuple[int, int], float]]],
    series_id: str,
    quarter: tuple[int, int],
) -> float | None:
    return {key: float(value) for key, value in data.get(series_id, [])}.get(quarter)


def _productivity_metrics(
    event: core.MarketEvent,
    now: datetime,
    refresh_token: str,
) -> list[dict[str, Any]]:
    reference = getattr(event, "reference_quarter", None)
    if not (isinstance(reference, tuple) and len(reference) == 2):
        return []
    previous_ref = _previous_quarter(reference)
    ids = list(PRODUCTIVITY_SERIES.values())
    data = phase2._bls_quarter_observations(ids, now, refresh_token)
    released = now >= event.time_tpe
    specs = (
        (
            "labor_productivity_qoq_saar", "非農企業勞動生產力 QoQ SAAR",
            PRODUCTIVITY_SERIES["labor_productivity"], True,
        ),
        (
            "unit_labor_costs_qoq_saar", "非農企業單位勞動成本 QoQ SAAR",
            PRODUCTIVITY_SERIES["unit_labor_costs"], False,
        ),
    )
    metrics: list[dict[str, Any]] = []
    for metric_id, label, series_id, primary in specs:
        current = _quarter_value(data, series_id, reference)
        previous = _quarter_value(data, series_id, previous_ref)
        actual_text = backend._pct(current) if released and current is not None else ""
        previous_text = backend._pct(previous) if previous is not None else ""
        if actual_text or previous_text:
            metrics.append(
                _metric(
                    metric_id,
                    label,
                    actual=actual_text,
                    previous=previous_text,
                    unit="% SAAR",
                    is_primary=primary,
                    source_series=series_id,
                )
            )
    return metrics


def _productivity_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    schedule, live_ok = _productivity_schedule(refresh_token)
    now = datetime.now(backend.TPE)
    events: list[core.MarketEvent] = []
    for reference, release_day in schedule:
        dt = backend._dt_local(release_day, 8, 30, backend.NY)
        if not backend._in_window(dt, start, end):
            continue
        event = backend._event(
            event_id=f"official-us-bls-productivity-{release_day.isoformat()}",
            dt=dt,
            title="美國勞動生產力與單位勞動成本（Productivity & Costs）",
            country="美國",
            tier="B",
            tags=("美國", "生產力", "單位勞動成本", "工資", "通膨", "Fed"),
            source="U.S. Bureau of Labor Statistics (BLS)",
            source_url=BLS_PRODUCTIVITY_SCHEDULE_URL,
            provider="official-us-bls-productivity",
            category="總體經濟",
            importance=2,
        )
        object.__setattr__(event, "reference_quarter", reference)
        metrics = _productivity_metrics(event, now, refresh_token)
        events.append(_with_metrics(event, metrics) if metrics else event)
    return events, bool(live_ok or PRODUCTIVITY_2026)


def _us_bls_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    events, ok = _BASE_US_BLS_EVENTS(start, end, refresh_token)
    productivity, productivity_ok = _productivity_events(start, end, refresh_token)
    return core._dedupe([*events, *productivity]), bool(ok or productivity_ok)


def _calibrate_gdp_event(event: core.MarketEvent) -> core.MarketEvent:
    if event.provider != "official-us-bea-gdp":
        return event
    lower = event.title.lower()
    if "advance" in lower:
        return _with_tags(replace(event, tier="A", importance=3), "GDP初值")
    if "second" in lower or "third" in lower:
        return _with_tags(replace(event, tier="B", importance=2), "GDP修正估值")
    return event


def _us_bea_schedule(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    events, ok = _BASE_US_BEA_SCHEDULE(start, end, refresh_token)
    return [_calibrate_gdp_event(event) for event in events], ok


def _enrich_fomc_decision(event: core.MarketEvent) -> core.MarketEvent:
    decision_day = event.time_tpe.astimezone(backend.NY).date()
    tags = ["含記者會"]
    if decision_day.month in {3, 6, 9, 12}:
        tags.append("SEP")
    return _with_tags(event, *tags)


def _fomc_minutes_event(decision: core.MarketEvent) -> core.MarketEvent:
    decision_day = decision.time_tpe.astimezone(backend.NY).date()
    release_day = decision_day + timedelta(days=21)
    dt = backend._dt_local(release_day, 14, 0, backend.NY)
    return backend._event(
        event_id=f"official-us-fed-fomc-minutes-{release_day.isoformat()}",
        dt=dt,
        title="美國FOMC會議紀要（Minutes）",
        country="美國",
        tier="A",
        tags=("美國", "FOMC", "Minutes", "Fed", "利率", "政策路徑"),
        source="Federal Reserve",
        source_url=backend.FED_FOMC_URL,
        provider="official-us-fed-fomc-minutes",
        category="央行事件",
        importance=2,
        expects_result=False,
    )


def _us_fomc_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    decisions, ok = _BASE_US_FOMC_EVENTS(start - timedelta(days=21), end, refresh_token)
    result: list[core.MarketEvent] = []
    for decision in decisions:
        if backend._in_window(decision.time_tpe, start, end):
            result.append(_enrich_fomc_decision(decision))
        minutes = _fomc_minutes_event(decision)
        if backend._in_window(minutes.time_tpe, start, end):
            result.append(minutes)
    return core._dedupe(result), ok


def _month_iter(start_day: date, end_day: date) -> Iterable[tuple[int, int]]:
    year, month = start_day.year, start_day.month
    while (year, month) <= (end_day.year, end_day.month):
        yield year, month
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1


def _parse_clock(value: str) -> tuple[int, int] | None:
    match = re.search(r"\b(\d{1,2}):(\d{2})\s*([ap])\.?m\.?", str(value or ""), re.I)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour == 12:
        hour = 0
    if match.group(3).lower() == "p":
        hour += 12
    return hour, minute


def _is_current_chair_text(text: str) -> bool:
    lower = text.lower()
    if "vice chair" in lower or "vice chairman" in lower:
        return False
    return bool(re.search(r"\b(?:chair|chairman)\s+[A-Z]", text))


def _chair_relevance(text: str) -> tuple[bool, str]:
    lower = text.lower()
    if any(token in lower for token in ("acceptance remarks", "award", "welcome remarks", "commencement")):
        return False, ""
    if "testimony" in lower or "monetary policy report to the congress" in lower:
        return True, "A"
    if "jackson hole" in lower or "economic policy symposium" in lower or "monetary policy framework" in lower:
        return True, "S"
    policy_terms = (
        "monetary policy", "economic outlook", "economy", "inflation", "employment",
        "labor market", "financial conditions", "financial stability", "policy outlook",
    )
    if any(term in lower for term in policy_terms):
        return True, "A"
    return False, ""


def _extract_row_day(row: list[str]) -> int | None:
    for cell in reversed(row):
        text = str(cell).strip()
        if re.fullmatch(r"\d{1,2}", text):
            day = int(text)
            if 1 <= day <= 31:
                return day
    return None


def _extract_topic(row: list[str]) -> str:
    candidates: list[str] = []
    for cell in row:
        text = " ".join(str(cell).split())
        lower = text.lower()
        if not text or _parse_clock(text) or re.fullmatch(r"\d{1,2}", text):
            continue
        if "watch live" in lower or lower.startswith("at "):
            continue
        if any(prefix in lower for prefix in ("speech -", "discussion -", "testimony -", "remarks -", "panel discussion -")):
            continue
        candidates.append(text)
    return candidates[0] if candidates else ""


def _parse_fed_chair_rows(rows: Iterable[list[str]], year: int, month: int) -> list[core.MarketEvent]:
    result: list[core.MarketEvent] = []
    source_url = f"{FED_CALENDAR_BASE}/{year}-{_MONTH_NAMES[month - 1]}.htm"
    for row in rows:
        joined = " | ".join(str(cell) for cell in row)
        lower = joined.lower()
        if not _is_current_chair_text(joined):
            continue
        if not any(kind in lower for kind in ("speech", "discussion", "testimony", "remarks", "panel")):
            continue
        relevant, tier = _chair_relevance(joined)
        if not relevant:
            continue
        day = _extract_row_day(list(row))
        clock = next((_parse_clock(cell) for cell in row if _parse_clock(cell)), None)
        if day is None or clock is None:
            continue
        try:
            release_day = date(year, month, day)
        except ValueError:
            continue
        dt = backend._dt_local(release_day, clock[0], clock[1], backend.NY)
        topic = _extract_topic(list(row))
        is_testimony = "testimony" in lower or "congress" in lower
        label = "Fed主席國會證詞" if is_testimony else "Fed主席重大政策談話"
        title = f"{label}－{topic}" if topic else label
        result.append(
            backend._event(
                event_id=f"official-us-fed-chair-{release_day.isoformat()}-{clock[0]:02d}{clock[1]:02d}",
                dt=dt,
                title=title,
                country="美國",
                tier=tier,
                tags=("美國", "Fed Chair", "貨幣政策", "利率", "全球風險資產"),
                source="Federal Reserve Board",
                source_url=source_url,
                provider="official-us-fed-chair",
                category="央行事件",
                importance=3 if tier == "S" else 2,
                expects_result=False,
            )
        )
    return core._dedupe(result)


def _fed_chair_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    start_day = start.astimezone(backend.NY).date()
    end_day = end.astimezone(backend.NY).date()
    result: list[core.MarketEvent] = []
    fetched_any = False
    for year, month in _month_iter(start_day, end_day):
        url = f"{FED_CALENDAR_BASE}/{year}-{_MONTH_NAMES[month - 1]}.htm"
        html = backend._fetch_text(url, f"{refresh_token}-chair-{year}-{month:02d}")
        if not html:
            continue
        fetched_any = True
        result.extend(_parse_fed_chair_rows(backend._table_rows(html), year, month))
    return [event for event in core._dedupe(result) if backend._in_window(event.time_tpe, start, end)], fetched_any


def collect_official_macro(
    start: datetime,
    end: datetime,
    refresh_token: str,
) -> tuple[list[core.MarketEvent], dict[str, bool]]:
    events, health = _BASE_COLLECT_OFFICIAL_MACRO(start, end, refresh_token)
    ism, ism_ok = _ism_events(start, end, refresh_token)
    chair, chair_ok = _fed_chair_events(start, end, refresh_token)
    health = dict(health)
    health["us_ism"] = ism_ok
    health["us_fed_chair"] = chair_ok
    return core._dedupe([*events, *ism, *chair]), health


def install() -> None:
    backend._us_bls_events = _us_bls_events
    backend._us_bea_schedule = _us_bea_schedule
    backend._us_fomc_events = _us_fomc_events
    backend.collect_official_macro = collect_official_macro


install()
