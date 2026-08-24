from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import v2_event_official as backend
import v2_event_radar as core

TW_CPI_SCHEDULE_URL = (
    "https://www.stat.gov.tw/News_NoticeCalendar.aspx?Dept=315000000H&"
    "PageSize=10&n=3717&page=2&sms=11505"
)
TW_GDP_SCHEDULE_URL = "https://www.stat.gov.tw/News_NoticeCalendar.aspx?Dept=315000000H&n=3717"

# Local copies of the 2026 dates published by DGBAS. They are used only if the
# live first-party calendar is temporarily unavailable or its pagination changes.
TW_CPI_2026 = (
    date(2026, 1, 7), date(2026, 2, 5), date(2026, 3, 6), date(2026, 4, 8),
    date(2026, 5, 7), date(2026, 6, 5), date(2026, 7, 7), date(2026, 8, 6),
    date(2026, 9, 8), date(2026, 10, 7), date(2026, 11, 5), date(2026, 12, 8),
)
TW_GDP_ADVANCE_2026 = (
    date(2026, 1, 30), date(2026, 4, 30), date(2026, 7, 31), date(2026, 10, 30),
)


def _tw_schedule_from_row(row: list[str], family: str, now: datetime) -> list[core.MarketEvent]:
    if family == "cpi":
        if not any("消費者物價指數" in cell for cell in row):
            return []
        title, tier, tags = "台灣消費者物價指數（CPI）", "S", ("台灣", "CPI", "通膨", "台股", "央行")
    else:
        # Use only the quarterly advance GDP estimate. The detailed national-accounts row
        # contains quarter ranges (Q1~Q2) and would otherwise create false duplicate events.
        if not any("國民所得概估統計" in cell for cell in row):
            return []
        title, tier, tags = "台灣國內生產毛額（GDP）概估", "A", ("台灣", "GDP", "景氣", "台股")

    result: list[core.MarketEvent] = []
    for cell in row[3:] if len(row) > 3 else row:
        if family == "cpi":
            match = re.search(
                r"(?<!\d)(\d{1,2})\s+(\d{1,2}):(\d{2})\s*\((\d{3})(\d{2})\)",
                cell,
            )
            if not match:
                continue
            release_day, hh, mm = int(match.group(1)), int(match.group(2)), int(match.group(3))
            ref_year = backend._roc_year_to_ad(int(match.group(4)))
            ref_month = int(match.group(5))
            release_year, release_month = ref_year, ref_month + 1
            if release_month == 13:
                release_year += 1
                release_month = 1
        else:
            match = re.search(
                r"(?<!\d)(\d{1,2})(?:日以前)?\s+(\d{1,2}):(\d{2})\s*\((\d{3})Q([1-4])\)",
                cell,
                re.I,
            )
            if not match:
                continue
            release_day, hh, mm = int(match.group(1)), int(match.group(2)), int(match.group(3))
            ref_year = backend._roc_year_to_ad(int(match.group(4)))
            quarter = int(match.group(5))
            release_month = {1: 4, 2: 7, 3: 10, 4: 1}[quarter]
            release_year = ref_year + (1 if quarter == 4 else 0)

        try:
            dt = backend._dt_local(date(release_year, release_month, release_day), hh, mm, backend.TPE)
        except ValueError:
            continue
        actual = previous = ""
        if datetime.now(backend.TPE) >= dt + timedelta(minutes=5):
            actual, previous = backend._tw_latest_result(family, refresh_token=f"tw-{now:%Y%m%d%H%M}")
        result.append(
            backend._event(
                event_id=f"official-tw-dgbas-{family}-{dt:%Y%m%d}",
                dt=dt,
                title=title,
                country="台灣",
                tier=tier,
                tags=tags,
                source="行政院主計總處",
                source_url=TW_CPI_SCHEDULE_URL if family == "cpi" else TW_GDP_SCHEDULE_URL,
                provider=f"official-tw-dgbas-{family}",
                actual=actual,
                previous=previous,
            )
        )
    return result


def _static_events(family: str, start: datetime, end: datetime, refresh_token: str) -> list[core.MarketEvent]:
    now = datetime.now(backend.TPE)
    days = TW_CPI_2026 if family == "cpi" else TW_GDP_ADVANCE_2026
    title = "台灣消費者物價指數（CPI）" if family == "cpi" else "台灣國內生產毛額（GDP）概估"
    tier = "S" if family == "cpi" else "A"
    tags = ("台灣", "CPI", "通膨", "台股", "央行") if family == "cpi" else ("台灣", "GDP", "景氣", "台股")
    result: list[core.MarketEvent] = []
    for release_day in days:
        dt = backend._dt_local(release_day, 16, 0, backend.TPE)
        if not backend._in_window(dt, start, end):
            continue
        actual = previous = ""
        if now >= dt + timedelta(minutes=5):
            actual, previous = backend._tw_latest_result(family, refresh_token)
        result.append(
            backend._event(
                event_id=f"official-tw-dgbas-{family}-{release_day:%Y%m%d}",
                dt=dt,
                title=title,
                country="台灣",
                tier=tier,
                tags=tags,
                source="行政院主計總處",
                source_url=TW_CPI_SCHEDULE_URL if family == "cpi" else TW_GDP_SCHEDULE_URL,
                provider=f"official-tw-dgbas-{family}",
                actual=actual,
                previous=previous,
            )
        )
    return result


def _tw_dgbas_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    backend.TW_CPI_SCHEDULE_URL = TW_CPI_SCHEDULE_URL
    backend.TW_GDP_SCHEDULE_URL = TW_GDP_SCHEDULE_URL
    now = datetime.now(backend.TPE)
    events: list[core.MarketEvent] = []

    cpi_html = backend._fetch_text(TW_CPI_SCHEDULE_URL, refresh_token)
    cpi_events: list[core.MarketEvent] = []
    if cpi_html:
        for row in backend._table_rows(cpi_html):
            cpi_events.extend(_tw_schedule_from_row(row, "cpi", now))
    if not cpi_events:
        cpi_events = _static_events("cpi", start, end, refresh_token)

    gdp_html = backend._fetch_text(TW_GDP_SCHEDULE_URL, refresh_token)
    gdp_events: list[core.MarketEvent] = []
    if gdp_html:
        for row in backend._table_rows(gdp_html):
            gdp_events.extend(_tw_schedule_from_row(row, "gdp", now))
    if not gdp_events:
        gdp_events = _static_events("gdp", start, end, refresh_token)

    events.extend(e for e in cpi_events if backend._in_window(e.time_tpe, start, end))
    events.extend(e for e in gdp_events if backend._in_window(e.time_tpe, start, end))
    return core._dedupe(events), bool(cpi_html or gdp_html or TW_CPI_2026)


def install() -> None:
    backend.TW_CPI_SCHEDULE_URL = TW_CPI_SCHEDULE_URL
    backend.TW_GDP_SCHEDULE_URL = TW_GDP_SCHEDULE_URL
    backend._tw_schedule_from_row = _tw_schedule_from_row
    backend._tw_dgbas_events = _tw_dgbas_events


install()
