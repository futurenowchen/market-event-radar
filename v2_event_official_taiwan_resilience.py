from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
import re

import v2_event_official as backend
import v2_event_radar as core

TW_PRICE_NEWS_URL = "https://www.stat.gov.tw/News.aspx?n=2668&sms=11023"
CBC_RATE_URL = "https://www.cbc.gov.tw/tw/lp-640-1-1-60.html"

_ORIGINAL_TW_LATEST_RESULT = backend._tw_latest_result
_ORIGINAL_TW_CBC_EVENTS = backend._tw_cbc_events


def _signed_tw_percent(direction: str | None, value: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""

    direction_text = str(direction or "").strip()
    if direction_text in {"跌", "下降", "減少"}:
        number = -abs(number)
    return backend._pct(number)


def _parse_cpi_yoy_values(text: str) -> list[str]:
    """Parse headline Taiwan CPI YoY values from DGBAS release titles/text.

    Current DGBAS wording is typically `CPI年增率漲2.04％`; the legacy parser
    only accepted `年增 2.04％`, which caused released values to remain blank.
    """
    pattern = re.compile(
        r"(?:消費者物價指數\s*(?:\(\s*CPI\s*\)|（\s*CPI\s*）)?|CPI)"
        r"[^。；\n%％]{0,120}?年增(?:率)?\s*"
        r"(漲|跌|增加|減少|上升|下降)?\s*"
        r"([+-]?\d+(?:\.\d+)?)\s*[％%]",
        re.I,
    )
    values: list[str] = []
    for direction, value in pattern.findall(text):
        parsed = _signed_tw_percent(direction, value)
        if parsed:
            values.append(parsed)
    return values


def _tw_latest_result(family: str, refresh_token: str) -> tuple[str, str]:
    if family != "cpi":
        return _ORIGINAL_TW_LATEST_RESULT(family, refresh_token)

    # Prefer the current DGBAS price-news listing. Fall back to the legacy page
    # used by the original collector if the current listing is unavailable.
    html = backend._fetch_text(TW_PRICE_NEWS_URL, refresh_token)
    values = _parse_cpi_yoy_values(backend._plain_text(html))

    if not values:
        legacy_html = backend._fetch_text(backend.TW_NEWS_URL, refresh_token)
        values = _parse_cpi_yoy_values(backend._plain_text(legacy_html))

    actual = values[0] if values else ""
    previous = values[1] if len(values) > 1 else ""
    return actual, previous


def _parse_cbc_rate_rows(html: str) -> list[tuple[date, str]]:
    """Parse the first-party CBC discount-rate history table.

    The live table currently uses Gregorian dates (YYYY/M/D). Accept ROC years
    as well so the parser does not depend on one presentation convention.
    """
    result: list[tuple[date, str]] = []
    for row in backend._table_rows(html):
        if len(row) < 2:
            continue
        day_match = re.fullmatch(r"\s*(\d{3,4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})\s*", row[0])
        if not day_match:
            continue
        year = int(day_match.group(1))
        if year < 1911:
            year = backend._roc_year_to_ad(year)
        try:
            day = date(year, int(day_match.group(2)), int(day_match.group(3)))
            rate = float(str(row[1]).strip().replace("%", "").replace("％", ""))
        except (TypeError, ValueError):
            continue
        result.append((day, backend._pct(rate)))
    return sorted(set(result), key=lambda item: item[0], reverse=True)


def _cbc_rate_before_meeting(rows: list[tuple[date, str]], meeting_day: date) -> str:
    for day, rate in rows:
        if day < meeting_day:
            return rate
    return ""


def _cbc_adjustment_near_meeting(
    rows: list[tuple[date, str]],
    meeting_day: date,
) -> str:
    """Return a newly-effective rate when the official table records one near the meeting."""
    upper = meeting_day + timedelta(days=3)
    candidates = [(day, rate) for day, rate in rows if meeting_day <= day <= upper]
    return max(candidates, default=(None, ""), key=lambda item: item[0])[1]


def _cbc_decision_matches_day(text: str, meeting_day: date) -> bool:
    plain = str(text or "")
    roc_year = meeting_day.year - 1911
    patterns = (
        meeting_day.isoformat(),
        f"{meeting_day.year}年{meeting_day.month}月{meeting_day.day}日",
        f"{roc_year}年{meeting_day.month}月{meeting_day.day}日",
    )
    return any(token in plain for token in patterns)


def _parse_cbc_discount_rate_from_decision(text: str) -> str:
    """Extract the discount rate from a CBC policy-decision release.

    Search only short clauses beginning at the explicit policy-rate label so
    unrelated percentages elsewhere in the economic discussion cannot win.
    """
    plain = backend._plain_text(text)
    for match in re.finditer(r"重貼現率", plain):
        clause = plain[match.start() : match.start() + 220]
        value = re.search(r"(\d+(?:\.\d+)?)\s*[％%]", clause)
        if value:
            return backend._pct(value.group(1))
    return ""


def _cbc_decision_holds_rate(text: str) -> bool:
    plain = backend._plain_text(text)
    patterns = (
        r"(?:政策|貼放)?利率[^。；]{0,100}?維持(?:不變|原水準)",
        r"維持[^。；]{0,40}?(?:政策|貼放)?利率(?:不變|原水準)",
        r"各項政策利率[^。；]{0,80}?不變",
    )
    return any(re.search(pattern, plain) for pattern in patterns)


def _cbc_decision_for_day(meeting_day: date, refresh_token: str) -> tuple[str, str]:
    """Return (decision_html, decision_url) for the requested CBC meeting day."""
    listing = backend._fetch_text(backend.CBC_MEETING_URL, refresh_token)
    if not listing:
        return "", ""

    candidates: list[str] = []
    for label, href in backend._links(listing, backend.CBC_MEETING_URL):
        normalized = " ".join(str(label or "").split())
        if "理監事" in normalized and ("決議" in normalized or "新聞稿" in normalized):
            candidates.append(href)

    # A listing can repeat the same link through desktop/mobile markup.
    for href in dict.fromkeys(candidates):
        html = backend._fetch_text(href, refresh_token)
        if html and _cbc_decision_matches_day(backend._plain_text(html), meeting_day):
            return html, href
    return "", ""


def _tw_cbc_events_resilient(
    start: datetime,
    end: datetime,
    refresh_token: str,
) -> tuple[list[core.MarketEvent], bool]:
    events, ok = _ORIGINAL_TW_CBC_EVENTS(start, end, refresh_token)
    if not events:
        return events, ok

    now = datetime.now(backend.TPE)
    rate_rows: list[tuple[date, str]] | None = None
    enriched: list[core.MarketEvent] = []

    for event in events:
        if now < event.time_tpe + timedelta(minutes=5):
            enriched.append(event)
            continue
        if event.actual and event.previous:
            enriched.append(event)
            continue

        if rate_rows is None:
            rate_rows = _parse_cbc_rate_rows(
                backend._fetch_text(CBC_RATE_URL, refresh_token)
            )

        meeting_day = event.time_tpe.astimezone(backend.TPE).date()
        previous = event.previous or _cbc_rate_before_meeting(rate_rows, meeting_day)
        decision_html, decision_url = _cbc_decision_for_day(meeting_day, refresh_token)

        actual = event.actual
        if not actual and decision_html:
            actual = _parse_cbc_discount_rate_from_decision(decision_html)

        if not actual:
            actual = _cbc_adjustment_near_meeting(rate_rows, meeting_day)

        if not actual and decision_html and _cbc_decision_holds_rate(decision_html):
            # For an unchanged decision, the strict pre-meeting table value is
            # both Actual and Previous. This remains first-party and avoids
            # inferring a value merely because the table has not updated.
            actual = previous

        if actual and not previous:
            # Extremely old table history may not include a strictly prior row.
            # Only a release that explicitly states "unchanged" can justify
            # using the same value as Previous.
            if decision_html and _cbc_decision_holds_rate(decision_html):
                previous = actual

        if not actual:
            enriched.append(event)
            continue

        enriched.append(
            replace(
                event,
                actual=actual,
                previous=previous,
                status="released",
                source_url=decision_url or event.source_url,
            )
        )

    return core._dedupe(enriched), ok


def install() -> None:
    backend._tw_latest_result = _tw_latest_result
    backend._tw_cbc_events = _tw_cbc_events_resilient


install()
