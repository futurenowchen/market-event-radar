from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import v2_event_official as backend
import v2_event_radar as core


# Keep the country-specific page quirks isolated from the generic official-source
# collector. This module installs the hardened Taiwan/Japan schedule parsers when
# imported by the two production entry points (snapshot worker + Streamlit fallback).


def _tw_schedule_from_row(row: list[str], family: str, now: datetime) -> list[core.MarketEvent]:
    if family == "cpi":
        if not any("消費者物價指數" in cell for cell in row):
            return []
        title, tier, tags = "台灣消費者物價指數（CPI）", "S", ("台灣", "CPI", "通膨", "台股", "央行")
    else:
        if not any(("國民所得" in cell or "國內生產毛額" in cell) for cell in row):
            return []
        title, tier, tags = "台灣國內生產毛額（GDP）", "A", ("台灣", "GDP", "景氣", "台股")

    cells = row[3:] if len(row) > 3 else row
    result: list[core.MarketEvent] = []
    for cell in cells:
        if family == "cpi":
            # DGBAS monthly cells look like: "6 16:00 (11507)".
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
            # DGBAS GDP cells use quarter periods, e.g. "31 16:00 (115Q2)".
            match = re.search(
                r"(?<!\d)(\d{1,2})(?:日以前)?\s+(\d{1,2}):(\d{2})\s*\((\d{3})Q([1-4])(?:[^)]*)?\)",
                cell,
                re.I,
            )
            if not match:
                continue
            release_day, hh, mm = int(match.group(1)), int(match.group(2)), int(match.group(3))
            ref_year = backend._roc_year_to_ad(int(match.group(4)))
            quarter = int(match.group(5))
            release_month = {1: 5, 2: 8, 3: 11, 4: 2}[quarter]
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
                source_url=backend.TW_CPI_SCHEDULE_URL if family == "cpi" else backend.TW_GDP_SCHEDULE_URL,
                provider=f"official-tw-dgbas-{family}",
                actual=actual,
                previous=previous,
            )
        )
    return result


def _jp_gdp_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    html = backend._fetch_text(backend.JP_GDP_SCHEDULE_URL, refresh_token)
    if not html:
        return [], False

    events: list[core.MarketEvent] = []
    for row in backend._table_rows(html):
        joined = " | ".join(row)
        lower = joined.lower()
        # ESRI uses reporting periods such as "Apr.-Jun. 2026" rather than the word "Quarter".
        if "preliminary" not in lower or not re.search(
            r"(?:Jan|Apr|Jul|Oct)\.-(?:Mar|Jun|Sep|Dec)\.\s+20\d{2}", joined, re.I
        ):
            continue

        date_match = re.search(
            r"((?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+[A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
            joined,
        )
        time_match = re.search(r"(\d{1,2}:\d{2})\s*(AM|PM)", joined, re.I)
        if not date_match:
            continue
        day = backend._parse_english_date(date_match.group(1), start.year)
        if day is None:
            continue

        if time_match:
            local_time = datetime.strptime(f"{time_match.group(1)} {time_match.group(2)}", "%I:%M %p").time()
            dt = datetime.combine(day, local_time, tzinfo=backend.JST).astimezone(backend.TPE)
        else:
            dt = backend._dt_local(day, 8, 50, backend.JST)
        if not backend._in_window(dt, start, end):
            continue

        period_match = re.search(
            r"((?:Jan|Apr|Jul|Oct)\.-(?:Mar|Jun|Sep|Dec)\.\s+20\d{2})",
            joined,
            re.I,
        )
        estimate = (
            "第一次速報"
            if "first preliminary" in lower
            else "第二次速報"
            if "second preliminary" in lower
            else "速報"
        )
        suffix = f"{period_match.group(1)} {estimate}" if period_match else estimate

        events.append(
            backend._event(
                event_id=f"official-jp-esri-gdp-{day.isoformat()}",
                dt=dt,
                title=f"日本國內生產毛額（GDP）－{suffix}",
                country="日本",
                tier="A",
                tags=("日本", "GDP", "景氣", "BOJ", "日股"),
                source="Cabinet Office, Government of Japan (ESRI)",
                source_url=backend.JP_GDP_SCHEDULE_URL,
                provider="official-jp-esri-gdp",
                # ESRI schedule is stable, but result extraction is deliberately not guessed.
                expects_result=False,
            )
        )
    return core._dedupe(events), True


def _jp_boj_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    text = backend._plain_text(backend._fetch_text(backend.BOJ_MPM_URL, refresh_token))
    if not text:
        return [], False

    events: list[core.MarketEvent] = []
    for year in sorted({start.year, end.year}):
        # The page has year navigation links before the tables. Anchor on "Table : YYYY"
        # so those links cannot truncate the section.
        section_match = re.search(
            rf"Table\s*:\s*{year}(.*?)(?=Table\s*:\s*{year + 1}|$)",
            text,
            re.I,
        )
        section = section_match.group(1) if section_match else ""
        for match in re.finditer(
            r"\b(Jan|Mar|Apr|June|July|Sept|Oct|Dec)\.?(?:\s+\d{1,2}\s*\([^)]*\),)?\s*(\d{1,2})\s*\([^)]*\)",
            section,
            re.I,
        ):
            month = backend._month_number(match.group(1))
            if month is None:
                continue
            try:
                day = date(year, month, int(match.group(2)))
            except ValueError:
                continue

            # BOJ states that the policy statement is released immediately after the MPM,
            # without a fixed minute. Noon JST is only a display marker; no 5-minute polling.
            dt = backend._dt_local(day, 12, 0, backend.JST)
            if not backend._in_window(dt, start, end):
                continue
            events.append(
                backend._event(
                    event_id=f"official-jp-boj-{day.isoformat()}",
                    dt=dt,
                    title="日本銀行（BOJ）金融政策決定會合",
                    country="日本",
                    tier="S",
                    tags=("日本", "BOJ", "利率", "日圓", "全球風險資產"),
                    source="Bank of Japan",
                    source_url=backend.BOJ_MPM_URL,
                    provider="official-jp-boj",
                    category="央行事件",
                    expects_result=False,
                )
            )
    return core._dedupe(events), True


def install() -> None:
    backend._tw_schedule_from_row = _tw_schedule_from_row
    backend._jp_gdp_events = _jp_gdp_events
    backend._jp_boj_events = _jp_boj_events


install()
