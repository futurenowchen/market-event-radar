from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any

import v2_event_official as backend
import v2_event_official_us_high_signal  # noqa: F401  # ensure Phase 1 wrappers are installed first
import v2_event_radar as core


JOLTS_SCHEDULE_URL = "https://www.bls.gov/schedule/news_release/jolts.htm"
ECI_SCHEDULE_URL = "https://www.bls.gov/schedule/news_release/eci.htm"
CENSUS_CALENDAR_URL = "https://www.census.gov/economic-indicators/calendar-listview.html"
RETAIL_SALES_URL = "https://www.census.gov/retail/sales.html"
CLAIMS_RELEASES_URL = "https://www.dol.gov/newsroom/releases/eta"

JOLTS_SERIES = {
    "openings": "JTS000000000000000JOL",
    "hires": "JTS000000000000000HIL",
    "quits": "JTS000000000000000QUL",
    "layoffs": "JTS000000000000000LDL",
}

ECI_SERIES = {
    "comp_qoq": "CIS1010000000000Q",
    "wages_qoq": "CIS1020000000000Q",
    "comp_yoy": "CIU1010000000000A",
    "wages_yoy": "CIU1020000000000A",
}

# Official 2026 calendars copied from the agencies as deterministic fallbacks.
# Live first-party schedules remain primary and can override these rows.
JOLTS_2026 = (
    (date(2025, 11, 1), date(2026, 1, 7)),
    (date(2025, 12, 1), date(2026, 2, 5)),
    (date(2026, 1, 1), date(2026, 3, 13)),
    (date(2026, 2, 1), date(2026, 3, 31)),
    (date(2026, 3, 1), date(2026, 5, 5)),
    (date(2026, 4, 1), date(2026, 6, 2)),
    (date(2026, 5, 1), date(2026, 6, 30)),
    (date(2026, 6, 1), date(2026, 8, 4)),
    (date(2026, 7, 1), date(2026, 9, 1)),
    (date(2026, 8, 1), date(2026, 9, 29)),
    (date(2026, 9, 1), date(2026, 11, 3)),
    (date(2026, 10, 1), date(2026, 12, 1)),
)

ECI_2026 = (
    ((2025, 4), date(2026, 2, 10)),
    ((2026, 1), date(2026, 4, 30)),
    ((2026, 2), date(2026, 7, 31)),
    ((2026, 3), date(2026, 10, 30)),
)

RETAIL_2026 = (
    (date(2025, 11, 1), date(2026, 1, 14)),
    (date(2025, 12, 1), date(2026, 2, 10)),
    (date(2026, 1, 1), date(2026, 3, 6)),
    (date(2026, 2, 1), date(2026, 4, 1)),
    (date(2026, 3, 1), date(2026, 4, 21)),
    (date(2026, 4, 1), date(2026, 5, 14)),
    (date(2026, 5, 1), date(2026, 6, 17)),
    (date(2026, 6, 1), date(2026, 7, 16)),
    (date(2026, 7, 1), date(2026, 8, 14)),
    (date(2026, 8, 1), date(2026, 9, 16)),
    (date(2026, 9, 1), date(2026, 10, 15)),
    (date(2026, 10, 1), date(2026, 11, 17)),
    (date(2026, 11, 1), date(2026, 12, 16)),
)

# DOL states that weekly claims are normally released Thursday at 08:30 ET;
# when a federal holiday conflicts, publication moves to the preceding Wednesday.
CLAIMS_HOLIDAY_OVERRIDES = {
    date(2026, 1, 1): date(2025, 12, 31),
    date(2026, 11, 26): date(2026, 11, 25),
}

_BASE_US_BLS_EVENTS = backend._us_bls_events
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


def _parse_release_day(value: str) -> date | None:
    text = " ".join(value.replace(".", "").split())
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_reference_month(value: str) -> date | None:
    match = re.search(r"([A-Za-z]+)\s+(20\d{2})", value)
    if not match:
        return None
    month = _MONTHS.get(match.group(1).lower().rstrip("."))
    if month is None:
        return None
    return date(int(match.group(2)), month, 1)


def _parse_reference_quarter(value: str) -> tuple[int, int] | None:
    text = " ".join(value.split()).lower()
    year_match = re.search(r"(20\d{2})", text)
    if not year_match:
        return None
    word_map = {"first": 1, "second": 2, "third": 3, "fourth": 4}
    for word, quarter in word_map.items():
        if word in text:
            return int(year_match.group(1)), quarter
    numeric = re.search(r"\b([1-4])(?:st|nd|rd|th)?\s+quarter\b", text)
    if numeric:
        return int(year_match.group(1)), int(numeric.group(1))
    return None


def _previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


def _previous_quarter(value: tuple[int, int]) -> tuple[int, int]:
    year, quarter = value
    return (year - 1, 4) if quarter == 1 else (year, quarter - 1)


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
    status = "released" if actual else event.status
    enriched = replace(event, actual=actual, previous=previous, status=status)
    if metrics:
        object.__setattr__(enriched, "metrics", tuple(dict(row) for row in metrics))
    return enriched


def _set_reference(event: core.MarketEvent, name: str, value: Any) -> core.MarketEvent:
    object.__setattr__(event, name, value)
    return event


def _fmt_millions_from_thousands(value: float | None) -> str:
    if value is None:
        return ""
    if abs(value) >= 1000:
        return f"{value / 1000:.1f}M"
    return f"{value:g}K"


def _fmt_claims(value: str | int | float | None) -> str:
    if value is None or value == "":
        return ""
    try:
        number = int(round(float(str(value).replace(",", ""))))
    except (TypeError, ValueError):
        return str(value).strip()
    return f"{number // 1000}K" if number % 1000 == 0 else f"{number / 1000:.1f}K"


def _signed_pct(direction: str, value: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if direction.strip().lower() == "down":
        number = -abs(number)
    return backend._pct(number)


def _series_value(data: dict[str, list[tuple[date, float]]], series_id: str, month: date) -> float | None:
    return {day: float(value) for day, value in data.get(series_id, [])}.get(month)


def _jolts_metrics(event: core.MarketEvent, now: datetime, refresh_token: str) -> list[dict[str, Any]]:
    reference = getattr(event, "reference_month", None)
    if not isinstance(reference, date):
        release_day = event.time_tpe.astimezone(backend.NY).date()
        reference = _previous_month(date(release_day.year, release_day.month, 1))
    previous_ref = _previous_month(reference)
    ids = list(JOLTS_SERIES.values())
    data = backend._bls_observations(ids, now, refresh_token)
    released = now >= event.time_tpe
    specs = (
        ("job_openings", "職缺數", JOLTS_SERIES["openings"], True),
        ("hires", "聘僱人數", JOLTS_SERIES["hires"], False),
        ("quits", "主動離職人數", JOLTS_SERIES["quits"], False),
        ("layoffs", "裁員與解僱人數", JOLTS_SERIES["layoffs"], False),
    )
    result: list[dict[str, Any]] = []
    for metric_id, label, series_id, primary in specs:
        current = _series_value(data, series_id, reference)
        previous = _series_value(data, series_id, previous_ref)
        actual_text = _fmt_millions_from_thousands(current) if released else ""
        previous_text = _fmt_millions_from_thousands(previous)
        if actual_text or previous_text:
            result.append(
                _metric(
                    metric_id,
                    label,
                    actual=actual_text,
                    previous=previous_text,
                    unit="level",
                    is_primary=primary,
                    source_series=series_id,
                )
            )
    return result


def _bls_quarter_observations(
    series_ids: list[str], now: datetime, refresh_token: str
) -> dict[str, list[tuple[tuple[int, int], float]]]:
    payload = {
        "seriesid": series_ids,
        "startyear": str(max(now.year - 2, 2024)),
        "endyear": str(now.year),
    }
    raw = backend._post_json(backend.BLS_API_URL, payload, refresh_token)
    results: dict[str, list[tuple[tuple[int, int], float]]] = {}
    for series in raw.get("Results", {}).get("series", []) if isinstance(raw, dict) else []:
        sid = str(series.get("seriesID") or "")
        values: list[tuple[tuple[int, int], float]] = []
        for row in series.get("data", []):
            period = str(row.get("period") or "")
            if not re.fullmatch(r"Q0[1-4]", period):
                continue
            try:
                key = (int(row.get("year")), int(period[-1]))
                value = float(str(row.get("value")).replace(",", ""))
            except (TypeError, ValueError):
                continue
            values.append((key, value))
        results[sid] = sorted(values)
    return results


def _eci_metrics(event: core.MarketEvent, now: datetime, refresh_token: str) -> list[dict[str, Any]]:
    reference = getattr(event, "reference_quarter", None)
    if not (isinstance(reference, tuple) and len(reference) == 2):
        release_day = event.time_tpe.astimezone(backend.NY).date()
        quarter = max(1, (release_day.month - 1) // 3)
        reference = (release_day.year, quarter)
    previous_ref = _previous_quarter(reference)
    data = _bls_quarter_observations(list(ECI_SERIES.values()), now, refresh_token)
    released = now >= event.time_tpe
    specs = (
        ("compensation_qoq", "總薪酬 QoQ", ECI_SERIES["comp_qoq"], True),
        ("wages_qoq", "薪資與工資 QoQ", ECI_SERIES["wages_qoq"], False),
        ("compensation_yoy", "總薪酬 YoY", ECI_SERIES["comp_yoy"], False),
        ("wages_yoy", "薪資與工資 YoY", ECI_SERIES["wages_yoy"], False),
    )
    result: list[dict[str, Any]] = []
    for metric_id, label, series_id, primary in specs:
        by_quarter = {key: float(value) for key, value in data.get(series_id, [])}
        current = by_quarter.get(reference)
        previous = by_quarter.get(previous_ref)
        actual_text = backend._pct(current) if released and current is not None else ""
        previous_text = backend._pct(previous) if previous is not None else ""
        if actual_text or previous_text:
            result.append(
                _metric(
                    metric_id,
                    label,
                    actual=actual_text,
                    previous=previous_text,
                    unit="%",
                    is_primary=primary,
                    source_series=series_id,
                )
            )
    return result


def _parse_retail_release_text(text: str) -> tuple[date | None, dict[str, str]]:
    match = re.search(
        r"Advance estimates of U\.S\. retail and food services sales for\s+"
        r"([A-Za-z]+)\s+(20\d{2}).{0,500}?were\s+\$?([\d,.]+)\s+billion,\s+"
        r"(up|down)\s+([0-9]+(?:\.[0-9]+)?)\s+percent.{0,180}?from the previous month,\s+"
        r"but\s+(up|down)\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        text,
        re.I,
    )
    if not match:
        return None, {}
    month = _MONTHS.get(match.group(1).lower())
    if month is None:
        return None, {}
    reference = date(int(match.group(2)), month, 1)
    values = {
        "sales_level": f"${float(match.group(3).replace(',', '')):g}B",
        "headline_mom": _signed_pct(match.group(4), match.group(5)),
        "headline_yoy": _signed_pct(match.group(6), match.group(7)),
        "previous_mom": "",
    }

    revised = re.search(
        r"percent change was revised from\s+(?:up|down)\s+[0-9]+(?:\.[0-9]+)?\s+percent"
        r".{0,120}?to\s+(up|down)\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        text,
        re.I,
    )
    if revised:
        values["previous_mom"] = _signed_pct(revised.group(1), revised.group(2))
    else:
        unrevised = re.search(
            r"percent change was unrevised from\s+(up|down)\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
            text,
            re.I,
        )
        if unrevised:
            values["previous_mom"] = _signed_pct(unrevised.group(1), unrevised.group(2))
    return reference, values


def _retail_metrics(event: core.MarketEvent, now: datetime, refresh_token: str) -> list[dict[str, Any]]:
    html = backend._fetch_text(RETAIL_SALES_URL, refresh_token)
    reference, values = _parse_retail_release_text(backend._plain_text(html))
    expected = getattr(event, "reference_month", None)
    if not isinstance(expected, date) or reference is None:
        return []
    released = now >= event.time_tpe and reference == expected
    if reference == expected:
        previous_mom = values.get("previous_mom", "")
    elif reference == _previous_month(expected):
        previous_mom = values.get("headline_mom", "")
    else:
        previous_mom = ""

    metrics: list[dict[str, Any]] = []
    actual_mom = values.get("headline_mom", "") if released else ""
    if actual_mom or previous_mom:
        metrics.append(
            _metric(
                "headline_mom",
                "零售與餐飲銷售 MoM",
                actual=actual_mom,
                previous=previous_mom,
                unit="%",
                is_primary=True,
                source_series="Census MARTS",
            )
        )
    if released and values.get("headline_yoy"):
        metrics.append(
            _metric(
                "headline_yoy",
                "零售與餐飲銷售 YoY",
                actual=values["headline_yoy"],
                unit="%",
                source_series="Census MARTS",
            )
        )
    if released and values.get("sales_level"):
        metrics.append(
            _metric(
                "sales_level",
                "零售與餐飲銷售額",
                actual=values["sales_level"],
                unit="USD billions",
                source_series="Census MARTS",
            )
        )
    return metrics


def _parse_claims_release_text(text: str) -> tuple[date | None, dict[str, str]]:
    match = re.search(
        r"([A-Za-z]+\s+\d{1,2},\s+20\d{2})\s+Unemployment Insurance Weekly Claims Report"
        r".{0,400}?advance figure for seasonally adjusted initial claims was\s+([\d,]+),"
        r".{0,450}?previous week's level was revised[^.]{0,180}?to\s+([\d,]+)\."
        r".{0,220}?4-week moving average was\s+([\d,]+)",
        text,
        re.I,
    )
    if not match:
        return None, {}
    release_day = _parse_release_day(match.group(1))
    return release_day, {
        "initial_claims": _fmt_claims(match.group(2)),
        "previous_claims": _fmt_claims(match.group(3)),
        "four_week_average": _fmt_claims(match.group(4)),
    }


def _claims_metrics(event: core.MarketEvent, now: datetime, refresh_token: str) -> list[dict[str, Any]]:
    html = backend._fetch_text(CLAIMS_RELEASES_URL, refresh_token)
    latest_day, values = _parse_claims_release_text(backend._plain_text(html))
    if latest_day is None:
        return []
    event_day = event.time_tpe.astimezone(backend.NY).date()
    released = now >= event.time_tpe and latest_day == event_day
    previous = ""
    if released:
        previous = values.get("previous_claims", "")
    elif latest_day < event_day:
        previous = values.get("initial_claims", "")
    actual = values.get("initial_claims", "") if released else ""
    result = []
    if actual or previous:
        result.append(
            _metric(
                "initial_claims",
                "初領失業救濟金",
                actual=actual,
                previous=previous,
                unit="K",
                is_primary=True,
                source_series="DOL ETA weekly claims",
            )
        )
    if released and values.get("four_week_average"):
        result.append(
            _metric(
                "four_week_average",
                "4週移動平均",
                actual=values["four_week_average"],
                unit="K",
                source_series="DOL ETA weekly claims",
            )
        )
    return result


def _jolts_schedule(refresh_token: str) -> tuple[list[tuple[date, date]], bool]:
    html = backend._fetch_text(JOLTS_SCHEDULE_URL, refresh_token)
    rows: list[tuple[date, date]] = []
    if html:
        for row in backend._table_rows(html):
            if len(row) < 2:
                continue
            reference = _parse_reference_month(row[0])
            release_day = _parse_release_day(row[1])
            if reference and release_day:
                rows.append((reference, release_day))
    return (sorted(set(rows)) if rows else list(JOLTS_2026), bool(rows))


def _eci_schedule(refresh_token: str) -> tuple[list[tuple[tuple[int, int], date]], bool]:
    html = backend._fetch_text(ECI_SCHEDULE_URL, refresh_token)
    rows: list[tuple[tuple[int, int], date]] = []
    if html:
        for row in backend._table_rows(html):
            if len(row) < 2:
                continue
            reference = _parse_reference_quarter(row[0])
            release_day = _parse_release_day(row[1])
            if reference and release_day:
                rows.append((reference, release_day))
    return (sorted(set(rows)) if rows else list(ECI_2026), bool(rows))


def _retail_schedule(refresh_token: str) -> tuple[list[tuple[date, date]], bool]:
    html = backend._fetch_text(CENSUS_CALENDAR_URL, refresh_token)
    rows: list[tuple[date, date]] = []
    if html:
        for row in backend._table_rows(html):
            joined = " | ".join(row)
            if "Advance Monthly Sales for Retail and Food Services" not in joined or len(row) < 4:
                continue
            release_day = next((_parse_release_day(cell) for cell in row if _parse_release_day(cell)), None)
            reference = next((_parse_reference_month(cell) for cell in row if _parse_reference_month(cell)), None)
            if reference and release_day:
                rows.append((reference, release_day))
    return (sorted(set(rows)) if rows else list(RETAIL_2026), bool(rows))


def _jolts_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    schedule, live_ok = _jolts_schedule(refresh_token)
    now = datetime.now(backend.TPE)
    events: list[core.MarketEvent] = []
    for reference, release_day in schedule:
        dt = backend._dt_local(release_day, 10, 0, backend.NY)
        if not backend._in_window(dt, start, end):
            continue
        event = backend._event(
            event_id=f"official-us-bls-jolts-{release_day.isoformat()}",
            dt=dt,
            title="美國職缺與勞動力流動調查（JOLTS）",
            country="美國",
            tier="A",
            tags=("美國", "JOLTS", "就業", "Fed", "NASDAQ"),
            source="U.S. Bureau of Labor Statistics (BLS)",
            source_url=JOLTS_SCHEDULE_URL,
            provider="official-us-bls-jolts",
        )
        _set_reference(event, "reference_month", reference)
        metrics = _jolts_metrics(event, now, refresh_token)
        events.append(_with_metrics(event, metrics) if metrics else event)
    return events, bool(live_ok or JOLTS_2026)


def _eci_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    schedule, live_ok = _eci_schedule(refresh_token)
    now = datetime.now(backend.TPE)
    events: list[core.MarketEvent] = []
    for reference, release_day in schedule:
        dt = backend._dt_local(release_day, 8, 30, backend.NY)
        if not backend._in_window(dt, start, end):
            continue
        event = backend._event(
            event_id=f"official-us-bls-eci-{release_day.isoformat()}",
            dt=dt,
            title="美國就業成本指數（ECI）",
            country="美國",
            tier="A",
            tags=("美國", "ECI", "薪資", "通膨", "Fed"),
            source="U.S. Bureau of Labor Statistics (BLS)",
            source_url=ECI_SCHEDULE_URL,
            provider="official-us-bls-eci",
        )
        _set_reference(event, "reference_quarter", reference)
        metrics = _eci_metrics(event, now, refresh_token)
        events.append(_with_metrics(event, metrics) if metrics else event)
    return events, bool(live_ok or ECI_2026)


def _retail_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    schedule, live_ok = _retail_schedule(refresh_token)
    now = datetime.now(backend.TPE)
    events: list[core.MarketEvent] = []
    for reference, release_day in schedule:
        dt = backend._dt_local(release_day, 8, 30, backend.NY)
        if not backend._in_window(dt, start, end):
            continue
        event = backend._event(
            event_id=f"official-us-census-retail-{release_day.isoformat()}",
            dt=dt,
            title="美國零售銷售（Retail Sales）",
            country="美國",
            tier="A",
            tags=("美國", "零售銷售", "消費", "景氣", "Fed", "NASDAQ"),
            source="U.S. Census Bureau",
            source_url=RETAIL_SALES_URL,
            provider="official-us-census-retail",
        )
        _set_reference(event, "reference_month", reference)
        metrics = _retail_metrics(event, now, refresh_token)
        events.append(_with_metrics(event, metrics) if metrics else event)
    return events, bool(live_ok or RETAIL_2026)


def _claims_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    del refresh_token
    start_day = start.astimezone(backend.NY).date() - timedelta(days=7)
    end_day = end.astimezone(backend.NY).date() + timedelta(days=7)
    now = datetime.now(backend.TPE)
    events: list[core.MarketEvent] = []
    day = start_day
    while day <= end_day:
        if day.weekday() == 3:
            release_day = CLAIMS_HOLIDAY_OVERRIDES.get(day, day)
            dt = backend._dt_local(release_day, 8, 30, backend.NY)
            if backend._in_window(dt, start, end):
                event = backend._event(
                    event_id=f"official-us-dol-claims-{release_day.isoformat()}",
                    dt=dt,
                    title="美國初領失業救濟金人數（Initial Claims）",
                    country="美國",
                    tier="A",
                    tags=("美國", "初領失業救濟", "就業", "Fed", "美元"),
                    source="U.S. Department of Labor (ETA)",
                    source_url=CLAIMS_RELEASES_URL,
                    provider="official-us-dol-claims",
                )
                metrics = _claims_metrics(event, now, f"claims-{release_day.isoformat()}")
                events.append(_with_metrics(event, metrics) if metrics else event)
        day += timedelta(days=1)
    return core._dedupe(events), bool(events)


def _us_bls_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    base_events, base_ok = _BASE_US_BLS_EVENTS(start, end, refresh_token)
    jolts, jolts_ok = _jolts_events(start, end, refresh_token)
    eci, eci_ok = _eci_events(start, end, refresh_token)
    return core._dedupe([*base_events, *jolts, *eci]), bool(base_ok or jolts_ok or eci_ok)


def collect_official_macro(
    start: datetime, end: datetime, refresh_token: str
) -> tuple[list[core.MarketEvent], dict[str, bool]]:
    events, health = _BASE_COLLECT_OFFICIAL_MACRO(start, end, refresh_token)
    retail, retail_ok = _retail_events(start, end, refresh_token)
    claims, claims_ok = _claims_events(start, end, refresh_token)
    health = dict(health)
    health["us_census"] = retail_ok
    health["us_dol"] = claims_ok
    return core._dedupe([*events, *retail, *claims]), health


def install() -> None:
    backend._us_bls_events = _us_bls_events
    backend.collect_official_macro = collect_official_macro


install()
