from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import v2_event_official as backend
import v2_event_radar as core

BLS_CPI_SCHEDULE_URL = "https://www.bls.gov/schedule/news_release/cpi.htm"
BLS_NFP_SCHEDULE_URL = "https://www.bls.gov/schedule/news_release/empsit.htm"
KR_CPI_SCHEDULE_URL = "https://mods.go.kr/cpiOaSchdlView.es?mid=b70203020000"
KR_INDUSTRY_SCHEDULE_URL = "https://mods.go.kr/boardDownload.es?bid=216&list_no=443302&seq=1"

# These are not inferred dates. They are a local safety copy of the agencies' published
# 2026 release calendars, used only when the first-party calendar endpoint rejects a
# GitHub-hosted runner. Live first-party schedules remain the preferred source.
BLS_2026 = {
    "cpi": (
        date(2026, 1, 13), date(2026, 2, 13), date(2026, 3, 11), date(2026, 4, 10),
        date(2026, 5, 12), date(2026, 6, 10), date(2026, 7, 14), date(2026, 8, 12),
        date(2026, 9, 11), date(2026, 10, 14), date(2026, 11, 10), date(2026, 12, 10),
    ),
    "nfp": (
        date(2026, 1, 9), date(2026, 2, 11), date(2026, 3, 6), date(2026, 4, 3),
        date(2026, 5, 8), date(2026, 6, 5), date(2026, 7, 2), date(2026, 8, 7),
        date(2026, 9, 4), date(2026, 10, 2), date(2026, 11, 6), date(2026, 12, 4),
    ),
}

KR_2026 = {
    "cpi": (
        date(2026, 2, 3), date(2026, 3, 6), date(2026, 4, 2), date(2026, 5, 6),
        date(2026, 6, 2), date(2026, 7, 2), date(2026, 8, 4), date(2026, 9, 2),
        date(2026, 10, 2), date(2026, 11, 3), date(2026, 12, 2), date(2026, 12, 31),
    ),
    "industry": (
        date(2026, 1, 30), date(2026, 3, 4), date(2026, 3, 31), date(2026, 4, 30),
        date(2026, 5, 29), date(2026, 6, 30), date(2026, 7, 31), date(2026, 8, 31),
        date(2026, 9, 30), date(2026, 10, 30), date(2026, 11, 30), date(2026, 12, 30),
    ),
}


def _parse_bls_release_day(value: str) -> date | None:
    text = " ".join(value.replace("Sept.", "Sep").replace("Sep.", "Sep").split())
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _bls_days_from_page(url: str, refresh_token: str) -> tuple[list[date], bool]:
    html = backend._fetch_text(url, refresh_token)
    if not html:
        return [], False
    days: list[date] = []
    for row in backend._table_rows(html):
        # Release-specific BLS tables are: Reference Month | Release Date | Release Time.
        if len(row) < 2:
            continue
        day = _parse_bls_release_day(row[1])
        if day is not None:
            days.append(day)
    return sorted(set(days)), bool(days)


def _us_bls_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    configs = {
        "cpi": {
            "url": BLS_CPI_SCHEDULE_URL,
            "title": "美國消費者物價指數（CPI）",
            "tags": ("美國", "通膨", "Fed", "NASDAQ", "台指"),
        },
        "nfp": {
            "url": BLS_NFP_SCHEDULE_URL,
            "title": "美國非農就業人數（NFP）",
            "tags": ("美國", "就業", "Fed", "美元", "NASDAQ"),
        },
    }
    events: list[core.MarketEvent] = []
    now = datetime.now(backend.TPE)
    any_live_schedule = False

    for family, cfg in configs.items():
        days, live_ok = _bls_days_from_page(str(cfg["url"]), refresh_token)
        any_live_schedule = any_live_schedule or live_ok
        if not days:
            days = list(BLS_2026.get(family, ()))

        for release_day in days:
            dt = backend._dt_local(release_day, 8, 30, backend.NY)
            if not backend._in_window(dt, start, end):
                continue
            actual = previous = ""
            if now >= dt + timedelta(minutes=5):
                actual, previous = backend._bls_latest_values(family, now, refresh_token)
            events.append(
                backend._event(
                    event_id=f"official-us-bls-{family}-{release_day.isoformat()}",
                    dt=dt,
                    title=str(cfg["title"]),
                    country="美國",
                    tier="S",
                    tags=tuple(cfg["tags"]),
                    source="U.S. Bureau of Labor Statistics (BLS)",
                    source_url=str(cfg["url"]),
                    provider=f"official-us-bls-{family}",
                    actual=actual,
                    previous=previous,
                )
            )

    # A published agency calendar embedded as a fallback is still a usable official schedule.
    # The live_schedule flag is separately exposed by the CI probe via direct fetch output.
    return core._dedupe(events), bool(any_live_schedule or BLS_2026)


def _parse_kr_schedule_rows(html: str, family: str, default_year: int) -> list[date]:
    days: list[date] = []
    for row in backend._table_rows(html):
        joined = " | ".join(row)
        if family == "cpi" and "소비자물가동향" not in joined:
            continue
        if family == "industry" and "산업활동동향" not in joined:
            continue

        # Supports both 2026. 8. 31. and 9.2. forms used by the official pages.
        full = re.search(r"(20\d{2})\s*[.년]\s*(\d{1,2})\s*[.월]\s*(\d{1,2})", joined)
        short = re.search(r"(?<!\d)(\d{1,2})\s*[.월]\s*(\d{1,2})(?:\s*[.일])?", joined)
        try:
            if full:
                days.append(date(int(full.group(1)), int(full.group(2)), int(full.group(3))))
            elif short:
                days.append(date(default_year, int(short.group(1)), int(short.group(2))))
        except ValueError:
            continue
    return sorted(set(days))


def _kr_mods_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    configs = {
        "cpi": {
            "url": KR_CPI_SCHEDULE_URL,
            "title": "韓國消費者物價指數（CPI）",
            "tier": "S",
            "tags": ("韓國", "CPI", "通膨", "BOK", "韓元"),
        },
        "industry": {
            "url": KR_INDUSTRY_SCHEDULE_URL,
            "title": "韓國工業生產",
            "tier": "A",
            "tags": ("韓國", "工業生產", "景氣", "半導體"),
        },
    }
    events: list[core.MarketEvent] = []
    now = datetime.now(backend.TPE)
    any_live_schedule = False

    for family, cfg in configs.items():
        html = backend._fetch_text(str(cfg["url"]), refresh_token)
        days = _parse_kr_schedule_rows(html, family, now.year) if html else []
        if days:
            any_live_schedule = True
        else:
            days = list(KR_2026.get(family, ()))

        for release_day in days:
            # Both official annual tables specify 08:00 KST publication time.
            dt = backend._dt_local(release_day, 8, 0, backend.KST)
            if not backend._in_window(dt, start, end):
                continue
            actual = previous = ""
            if now >= dt + timedelta(minutes=5):
                actual, previous = backend._kr_latest_result(family, refresh_token)
            events.append(
                backend._event(
                    event_id=f"official-kr-mods-{family}-{release_day.isoformat()}",
                    dt=dt,
                    title=str(cfg["title"]),
                    country="韓國",
                    tier=str(cfg["tier"]),
                    tags=tuple(cfg["tags"]),
                    source="Ministry of Data and Statistics, Korea",
                    source_url=str(cfg["url"]),
                    provider=f"official-kr-mods-{family}",
                    actual=actual,
                    previous=previous,
                )
            )

    return core._dedupe(events), bool(any_live_schedule or KR_2026)


def _signed_percent(direction: str, value: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if str(direction).strip().lower() == "decreased":
        number = -abs(number)
    return backend._pct(number)


def _parse_pce_yoy(text: str) -> str:
    match = re.search(
        r"from the same month one year ago,?\s+the PCE price index(?:\s+for\s+[A-Za-z]+)?\s+"
        r"(increased|decreased)\s+([0-9]+(?:\.[0-9]+)?)\s+percent",
        text,
        re.I,
    )
    if not match:
        match = re.search(
            r"PCE price index(?:\s+for\s+[A-Za-z]+)?\s+(increased|decreased)\s+"
            r"([0-9]+(?:\.[0-9]+)?)\s+percent\s+from one year ago",
            text,
            re.I,
        )
    return _signed_percent(match.group(1), match.group(2)) if match else ""


def _parse_gdp_annual_rate(text: str) -> str:
    match = re.search(
        r"real gross domestic product\s*\(gdp\)\s+(increased|decreased).*?annual rate of\s+"
        r"([0-9]+(?:\.[0-9]+)?)\s+percent",
        text,
        re.I,
    )
    if not match:
        match = re.search(
            r"real GDP\s+(increased|decreased).*?([0-9]+(?:\.[0-9]+)?)\s+percent",
            text,
            re.I,
        )
    return _signed_percent(match.group(1), match.group(2)) if match else ""


def _previous_pce_url(current_url: str) -> str:
    match = re.search(r"personal-income-and-outlays-([a-z]+)-(20\d{2})", current_url, re.I)
    if not match:
        return ""
    month_names = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    ]
    month = match.group(1).lower()
    year = int(match.group(2))
    if month not in month_names:
        return ""
    index = month_names.index(month)
    if index == 0:
        index = 11
        year -= 1
    else:
        index -= 1
    return f"https://www.bea.gov/news/{year}/personal-income-and-outlays-{month_names[index]}-{year}"


def _previous_gdp_url(current_url: str) -> str:
    if "gdp-second-estimate" in current_url:
        return current_url.replace("gdp-second-estimate-and-corporate-profits", "gdp-advance-estimate")
    if "gdp-third-estimate" in current_url:
        return current_url.replace("gdp-third-estimate-industries-corporate-profits", "gdp-second-estimate-and-corporate-profits")
    return ""


def _bea_latest_result(family: str, refresh_token: str) -> tuple[str, str]:
    """Parse BEA actual and previous-release values from first-party release pages."""
    listing = backend._fetch_text(backend.BEA_RELEASES_URL, refresh_token)
    if not listing:
        return "", ""

    href = ""
    for text, url in backend._links(listing, backend.BEA_RELEASES_URL):
        lower = text.lower()
        if family == "gdp" and "gdp" in lower and "estimate" in lower:
            href = url
            break
        if family == "pce" and "personal income and outlays" in lower:
            href = url
            break
    if not href:
        return "", ""

    current_text = backend._plain_text(backend._fetch_text(href, refresh_token))
    if family == "gdp":
        actual = _parse_gdp_annual_rate(current_text)
        previous_url = _previous_gdp_url(href)
        previous_text = backend._plain_text(backend._fetch_text(previous_url, refresh_token)) if previous_url else ""
        previous = _parse_gdp_annual_rate(previous_text)
        return actual, previous

    actual = _parse_pce_yoy(current_text)
    previous_url = _previous_pce_url(href)
    previous_text = backend._plain_text(backend._fetch_text(previous_url, refresh_token)) if previous_url else ""
    previous = _parse_pce_yoy(previous_text)
    return actual, previous


def install() -> None:
    backend._us_bls_events = _us_bls_events
    backend._kr_mods_events = _kr_mods_events
    backend._bea_latest_result = _bea_latest_result


install()
