from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, datetime
from typing import Any

import v2_event_official as backend
import v2_event_official_us_claims  # noqa: F401  # ensure Phase 2 + claims wrappers are installed first
import v2_event_radar as core


FED_G17_URL = "https://www.federalreserve.gov/releases/g17/"
FED_G17_CURRENT_URL = "https://www.federalreserve.gov/releases/g17/current/"
FED_G17_TABLE7_URL = "https://www.federalreserve.gov/releases/g17/current/table7.htm"
DURABLE_SCHEDULE_URL = "https://www.census.gov/manufacturing/m3/release_schedule.html"
DURABLE_CURRENT_URL = "https://www.census.gov/manufacturing/m3/adv/current/index.html"
HOUSING_SCHEDULE_URL = "https://www.census.gov/construction/soc/schedule.html"
HOUSING_CURRENT_URL = "https://www.census.gov/construction/nrc/current/"

G17_2026 = (
    date(2026, 1, 16), date(2026, 2, 18), date(2026, 3, 16), date(2026, 4, 16),
    date(2026, 5, 15), date(2026, 6, 15), date(2026, 7, 17), date(2026, 8, 18),
    date(2026, 9, 18), date(2026, 10, 16), date(2026, 11, 17), date(2026, 12, 16),
)

DURABLE_2026 = (
    (date(2025, 11, 1), date(2026, 1, 26)),
    (date(2025, 12, 1), date(2026, 2, 18)),
    (date(2026, 1, 1), date(2026, 3, 13)),
    (date(2026, 2, 1), date(2026, 4, 7)),
    (date(2026, 3, 1), date(2026, 4, 29)),
    (date(2026, 4, 1), date(2026, 5, 28)),
    (date(2026, 5, 1), date(2026, 6, 25)),
    (date(2026, 6, 1), date(2026, 7, 27)),
    (date(2026, 7, 1), date(2026, 8, 26)),
    (date(2026, 8, 1), date(2026, 9, 25)),
    (date(2026, 9, 1), date(2026, 10, 27)),
    (date(2026, 10, 1), date(2026, 11, 25)),
    (date(2026, 11, 1), date(2026, 12, 23)),
)

HOUSING_2026 = (
    (date(2026, 1, 1), date(2026, 3, 12)),
    (date(2026, 2, 1), date(2026, 4, 29)),
    (date(2026, 3, 1), date(2026, 4, 29)),
    (date(2026, 4, 1), date(2026, 5, 21)),
    (date(2026, 5, 1), date(2026, 6, 16)),
    (date(2026, 6, 1), date(2026, 7, 17)),
    (date(2026, 7, 1), date(2026, 8, 18)),
    (date(2026, 8, 1), date(2026, 9, 17)),
    (date(2026, 9, 1), date(2026, 10, 20)),
    (date(2026, 10, 1), date(2026, 11, 18)),
    (date(2026, 11, 1), date(2026, 12, 17)),
)

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


def _parse_date(value: str, year_hint: int | None = None) -> date | None:
    text = " ".join(str(value or "").replace(".", "").split())
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    if year_hint is not None:
        for fmt in ("%B %d", "%b %d", "%m/%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                return date(year_hint, parsed.month, parsed.day)
            except ValueError:
                continue
    return None


def _parse_reference_month(value: str) -> date | None:
    match = re.search(r"([A-Za-z]+)\s+(20\d{2})", str(value or ""))
    if not match:
        return None
    month = _MONTHS.get(match.group(1).lower().rstrip("."))
    if month is None:
        return None
    return date(int(match.group(2)), month, 1)


def _previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


def _reference_from_release_month(month_name: str, release_day: date) -> date | None:
    month = _MONTHS.get(month_name.lower().rstrip("."))
    if month is None:
        return None
    year = release_day.year if month <= release_day.month else release_day.year - 1
    return date(year, month, 1)


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


def _set_reference(event: core.MarketEvent, value: date) -> core.MarketEvent:
    object.__setattr__(event, "reference_month", value)
    return event


def _signed_pct(direction: str, value: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if direction.lower() in {"decreased", "decrease", "fell", "falling", "down", "below"}:
        number = -abs(number)
    return backend._pct(number)


def _fmt_level(value: str | int | float | None) -> str:
    if value is None or value == "":
        return ""
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return str(value).strip()
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.3f}M".rstrip("0").rstrip(".") + "M" if False else f"{number / 1_000_000:.3f}M"
    if abs(number) >= 1000:
        formatted = number / 1000
        return f"{formatted:.3f}".rstrip("0").rstrip(".") + "M"
    return f"{number:g}K"


def _fmt_billions(value: str | int | float | None) -> str:
    if value is None or value == "":
        return ""
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return str(value).strip()
    return f"${number:g}B"


def _g17_schedule(refresh_token: str) -> tuple[list[date], bool]:
    text = backend._plain_text(backend._fetch_text(FED_G17_URL, refresh_token))
    days: list[date] = []
    section = re.search(r"2026:\s*(.*?)(?:2027:|Historical Release Dates)", text, re.I)
    if section:
        for month_name, day_text in re.findall(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})",
            section.group(1),
            re.I,
        ):
            month = _MONTHS[month_name.lower()]
            try:
                days.append(date(2026, month, int(day_text)))
            except ValueError:
                continue
    return (sorted(set(days)) if days else list(G17_2026), bool(days))


def _durable_schedule(refresh_token: str) -> tuple[list[tuple[date, date]], bool]:
    html = backend._fetch_text(DURABLE_SCHEDULE_URL, refresh_token)
    rows: list[tuple[date, date]] = []
    if html:
        for row in backend._table_rows(html):
            if len(row) < 2:
                continue
            reference = _parse_reference_month(row[0])
            release_day = _parse_date(row[1])
            if reference and release_day:
                rows.append((reference, release_day))
    return (sorted(set(rows)) if rows else list(DURABLE_2026), bool(rows))


def _housing_schedule(refresh_token: str) -> tuple[list[tuple[date, date]], bool]:
    html = backend._fetch_text(HOUSING_SCHEDULE_URL, refresh_token)
    rows: list[tuple[date, date]] = []
    if html:
        for row in backend._table_rows(html):
            if len(row) < 2:
                continue
            reference = _parse_reference_month(row[0])
            release_day = _parse_date(row[1])
            if reference and release_day:
                rows.append((reference, release_day))
    return (sorted(set(rows)) if rows else list(HOUSING_2026), bool(rows))


def _parse_g17_release(text: str) -> tuple[date | None, dict[str, str]]:
    release_match = re.search(r"Release Date:\s*([A-Za-z]+\s+\d{1,2},\s+20\d{2})", text, re.I)
    release_day = _parse_date(release_match.group(1)) if release_match else None
    pattern = re.search(
        r"Industrial production(?:\s*\(IP\))?(?:\s+and\s+manufacturing production)?(?:\s+each)?\s+"
        r"(grew|fell|increased|decreased)\s+([0-9]+(?:\.[0-9]+)?)\s+percent\s+in\s+([A-Za-z]+)\s+"
        r"after\s+(?:growing|falling|increasing|decreasing)\s+([0-9]+(?:\.[0-9]+)?)\s+percent\s+in\s+([A-Za-z]+)",
        text,
        re.I,
    )
    if not pattern or release_day is None:
        return None, {}
    reference = _reference_from_release_month(pattern.group(3), release_day)
    return reference, {
        "ip_mom": _signed_pct(pattern.group(1), pattern.group(2)),
        "previous_ip_mom": _signed_pct(
            "decreased" if pattern.group(4).startswith("-") else "increased",
            pattern.group(4).lstrip("+-"),
        ),
    }


def _capacity_values(html: str) -> tuple[str, str]:
    for row in backend._table_rows(html):
        if not row or "total industry" not in row[0].lower():
            continue
        values: list[float] = []
        for cell in row[1:]:
            cleaned = str(cell).replace(",", "").strip()
            if re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
                try:
                    values.append(float(cleaned))
                except ValueError:
                    pass
        if len(values) >= 2:
            return backend._pct(values[-1]), backend._pct(values[-2])
    return "", ""


def _g17_metrics(event: core.MarketEvent, now: datetime, refresh_token: str) -> list[dict[str, Any]]:
    text = backend._plain_text(backend._fetch_text(FED_G17_CURRENT_URL, refresh_token))
    reference, values = _parse_g17_release(text)
    expected = getattr(event, "reference_month", None)
    if not isinstance(expected, date) or reference is None:
        return []
    capacity_current, capacity_previous = _capacity_values(
        backend._fetch_text(FED_G17_TABLE7_URL, refresh_token)
    )
    released = now >= event.time_tpe and reference == expected
    if reference == expected:
        ip_previous = values.get("previous_ip_mom", "")
        cap_previous = capacity_previous
    elif reference == _previous_month(expected):
        ip_previous = values.get("ip_mom", "")
        cap_previous = capacity_current
    else:
        return []

    metrics = [
        _metric(
            "industrial_production_mom",
            "工業生產 MoM",
            actual=values.get("ip_mom", "") if released else "",
            previous=ip_previous,
            unit="%",
            is_primary=True,
            source_series="Federal Reserve G.17 Total IP",
        )
    ]
    if (capacity_current and released) or cap_previous:
        metrics.append(
            _metric(
                "capacity_utilization",
                "產能利用率",
                actual=capacity_current if released else "",
                previous=cap_previous,
                unit="%",
                source_series="Federal Reserve G.17 Table 7 Total industry",
            )
        )
    return [m for m in metrics if m["actual"] or m["previous"]]


def _parse_durable_release(text: str) -> tuple[date | None, dict[str, str]]:
    release_match = re.search(
        r"(?:FOR IMMEDIATE RELEASE:\s*[A-Za-z]+,\s*)?([A-Za-z]+\s+\d{1,2},\s+20\d{2})",
        text,
        re.I,
    )
    release_day = _parse_date(release_match.group(1)) if release_match else None
    headline = re.search(
        r"New orders for manufactured durable goods in\s+([A-Za-z]+).*?"
        r"(increased|decreased)\s+\$?([0-9]+(?:\.[0-9]+)?)\s+billion\s+or\s+"
        r"([0-9]+(?:\.[0-9]+)?)\s+percent\s+to\s+\$?([0-9]+(?:\.[0-9]+)?)\s+billion\.\s+"
        r"This followed a\s+([0-9]+(?:\.[0-9]+)?)\s+percent\s+([A-Za-z]+)\s+(increase|decrease)",
        text,
        re.I,
    )
    if not headline or release_day is None:
        return None, {}
    reference = _reference_from_release_month(headline.group(1), release_day)
    if reference is None:
        return None, {}
    values = {
        "headline_mom": _signed_pct(headline.group(2), headline.group(4)),
        "previous_mom": _signed_pct(headline.group(8), headline.group(6)),
        "orders_level": _fmt_billions(headline.group(5)),
        "ex_transport_mom": "",
        "ex_defense_mom": "",
    }
    ex_transport = re.search(
        r"Excluding transportation,\s+new orders\s+(increased|decreased)\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        text,
        re.I,
    )
    if ex_transport:
        values["ex_transport_mom"] = _signed_pct(ex_transport.group(1), ex_transport.group(2))
    ex_defense = re.search(
        r"Excluding defense,\s+new orders\s+(increased|decreased)\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        text,
        re.I,
    )
    if ex_defense:
        values["ex_defense_mom"] = _signed_pct(ex_defense.group(1), ex_defense.group(2))
    return reference, values


def _durable_metrics(event: core.MarketEvent, now: datetime, refresh_token: str) -> list[dict[str, Any]]:
    text = backend._plain_text(backend._fetch_text(DURABLE_CURRENT_URL, refresh_token))
    reference, values = _parse_durable_release(text)
    expected = getattr(event, "reference_month", None)
    if not isinstance(expected, date) or reference is None:
        return []
    released = now >= event.time_tpe and reference == expected
    if reference == expected:
        previous = values.get("previous_mom", "")
    elif reference == _previous_month(expected):
        previous = values.get("headline_mom", "")
    else:
        return []

    metrics = [
        _metric(
            "durable_goods_orders_mom",
            "耐久財新訂單 MoM",
            actual=values.get("headline_mom", "") if released else "",
            previous=previous,
            unit="%",
            is_primary=True,
            source_series="Census M3 Advance Durable Goods",
        )
    ]
    if released:
        for metric_id, label, key in (
            ("ex_transport_mom", "扣除運輸設備 MoM", "ex_transport_mom"),
            ("ex_defense_mom", "扣除國防 MoM", "ex_defense_mom"),
            ("orders_level", "耐久財新訂單總額", "orders_level"),
        ):
            actual = values.get(key, "")
            if actual:
                metrics.append(
                    _metric(
                        metric_id,
                        label,
                        actual=actual,
                        unit="%" if metric_id.endswith("mom") else "USD billions",
                        source_series="Census M3 Advance Durable Goods",
                    )
                )
    return [m for m in metrics if m["actual"] or m["previous"]]


def _parse_housing_release(text: str) -> tuple[date | None, dict[str, str]]:
    header = re.search(
        r"MONTHLY NEW RESIDENTIAL CONSTRUCTION,\s+([A-Za-z]+)\s+(20\d{2})",
        text,
        re.I,
    )
    if not header:
        return None, {}
    month = _MONTHS.get(header.group(1).lower())
    if month is None:
        return None, {}
    reference = date(int(header.group(2)), month, 1)

    permits = re.search(
        r"Building Permits.*?authorized by building permits in\s+[A-Za-z]+\s+were at a seasonally adjusted annual rate of\s+"
        r"([\d,]+)\.\s+This is\s+([0-9]+(?:\.[0-9]+)?)\s+percent\s+(above|below)\s+the revised\s+"
        r"[A-Za-z]+\s+rate of\s+([\d,]+)",
        text,
        re.I,
    )
    starts = re.search(
        r"Housing Starts.*?housing starts in\s+[A-Za-z]+\s+were at a seasonally adjusted annual rate of\s+"
        r"([\d,]+)\.\s+This is\s+([0-9]+(?:\.[0-9]+)?)\s+percent(?:\s+\([^)]*\))?\*?\s+"
        r"(above|below)\s+the revised\s+[A-Za-z]+\s+estimate of\s+([\d,]+)",
        text,
        re.I,
    )
    if not starts:
        return reference, {}
    values = {
        "starts_level": _fmt_level(starts.group(1)),
        "starts_mom": _signed_pct(starts.group(3), starts.group(2)),
        "previous_starts_level": _fmt_level(starts.group(4)),
        "permits_level": "",
        "permits_mom": "",
        "previous_permits_level": "",
    }
    if permits:
        values.update(
            {
                "permits_level": _fmt_level(permits.group(1)),
                "permits_mom": _signed_pct(permits.group(3), permits.group(2)),
                "previous_permits_level": _fmt_level(permits.group(4)),
            }
        )
    return reference, values


def _housing_metrics(event: core.MarketEvent, now: datetime, refresh_token: str) -> list[dict[str, Any]]:
    text = backend._plain_text(backend._fetch_text(HOUSING_CURRENT_URL, refresh_token))
    reference, values = _parse_housing_release(text)
    expected = getattr(event, "reference_month", None)
    if not isinstance(expected, date) or reference is None:
        return []
    released = now >= event.time_tpe and reference == expected
    if reference == expected:
        starts_previous = values.get("previous_starts_level", "")
        permits_previous = values.get("previous_permits_level", "")
    elif reference == _previous_month(expected):
        starts_previous = values.get("starts_level", "")
        permits_previous = values.get("permits_level", "")
    else:
        return []

    metrics = [
        _metric(
            "housing_starts_saar",
            "新屋開工 SAAR",
            actual=values.get("starts_level", "") if released else "",
            previous=starts_previous,
            unit="annualized units",
            is_primary=True,
            source_series="Census/HUD New Residential Construction",
        ),
    ]
    if released and values.get("starts_mom"):
        metrics.append(
            _metric(
                "housing_starts_mom",
                "新屋開工 MoM",
                actual=values["starts_mom"],
                unit="%",
                source_series="Census/HUD New Residential Construction",
            )
        )
    if values.get("permits_level") and (released or permits_previous):
        metrics.append(
            _metric(
                "building_permits_saar",
                "建築許可 SAAR",
                actual=values.get("permits_level", "") if released else "",
                previous=permits_previous,
                unit="annualized units",
                source_series="Census/HUD New Residential Construction",
            )
        )
    if released and values.get("permits_mom"):
        metrics.append(
            _metric(
                "building_permits_mom",
                "建築許可 MoM",
                actual=values["permits_mom"],
                unit="%",
                source_series="Census/HUD New Residential Construction",
            )
        )
    return [m for m in metrics if m["actual"] or m["previous"]]


def _g17_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    schedule, live_ok = _g17_schedule(refresh_token)
    now = datetime.now(backend.TPE)
    events: list[core.MarketEvent] = []
    for release_day in schedule:
        dt = backend._dt_local(release_day, 9, 15, backend.NY)
        if not backend._in_window(dt, start, end):
            continue
        reference = _previous_month(date(release_day.year, release_day.month, 1))
        event = backend._event(
            event_id=f"official-us-fed-g17-{release_day.isoformat()}",
            dt=dt,
            title="美國工業生產與產能利用率（G.17）",
            country="美國",
            tier="B",
            tags=("美國", "工業生產", "產能利用率", "景氣", "Fed"),
            source="Federal Reserve Board",
            source_url=FED_G17_URL,
            provider="official-us-fed-g17",
            importance=2,
        )
        _set_reference(event, reference)
        metrics = _g17_metrics(event, now, refresh_token)
        events.append(_with_metrics(event, metrics) if metrics else event)
    return events, bool(live_ok or G17_2026)


def _durable_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    schedule, live_ok = _durable_schedule(refresh_token)
    now = datetime.now(backend.TPE)
    events: list[core.MarketEvent] = []
    for reference, release_day in schedule:
        dt = backend._dt_local(release_day, 8, 30, backend.NY)
        if not backend._in_window(dt, start, end):
            continue
        event = backend._event(
            event_id=f"official-us-census-durable-{release_day.isoformat()}",
            dt=dt,
            title="美國耐久財訂單（Durable Goods Orders）",
            country="美國",
            tier="B",
            tags=("美國", "耐久財", "製造業", "景氣", "資本支出"),
            source="U.S. Census Bureau",
            source_url=DURABLE_CURRENT_URL,
            provider="official-us-census-durable",
            importance=2,
        )
        _set_reference(event, reference)
        metrics = _durable_metrics(event, now, refresh_token)
        events.append(_with_metrics(event, metrics) if metrics else event)
    return events, bool(live_ok or DURABLE_2026)


def _housing_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    schedule, live_ok = _housing_schedule(refresh_token)
    now = datetime.now(backend.TPE)
    events: list[core.MarketEvent] = []
    for reference, release_day in schedule:
        dt = backend._dt_local(release_day, 8, 30, backend.NY)
        if not backend._in_window(dt, start, end):
            continue
        event = backend._event(
            event_id=f"official-us-census-housing-{release_day.isoformat()}",
            dt=dt,
            title="美國新屋開工與建築許可（Housing Starts / Permits）",
            country="美國",
            tier="B",
            tags=("美國", "房市", "新屋開工", "建築許可", "景氣", "利率"),
            source="U.S. Census Bureau / HUD",
            source_url=HOUSING_CURRENT_URL,
            provider="official-us-census-housing",
            importance=2,
        )
        _set_reference(event, reference)
        metrics = _housing_metrics(event, now, refresh_token)
        events.append(_with_metrics(event, metrics) if metrics else event)
    return events, bool(live_ok or HOUSING_2026)


def collect_official_macro(
    start: datetime, end: datetime, refresh_token: str
) -> tuple[list[core.MarketEvent], dict[str, bool]]:
    events, health = _BASE_COLLECT_OFFICIAL_MACRO(start, end, refresh_token)
    g17, g17_ok = _g17_events(start, end, refresh_token)
    durable, durable_ok = _durable_events(start, end, refresh_token)
    housing, housing_ok = _housing_events(start, end, refresh_token)
    health = dict(health)
    health["us_fed_g17"] = g17_ok
    health["us_census_m3"] = durable_ok
    health["us_census_housing"] = housing_ok
    return core._dedupe([*events, *g17, *durable, *housing]), health


def install() -> None:
    backend.collect_official_macro = collect_official_macro


install()
