from __future__ import annotations

import re

import v2_event_official as backend

TW_PRICE_NEWS_URL = "https://www.stat.gov.tw/News.aspx?n=2668&sms=11023"

_ORIGINAL_TW_LATEST_RESULT = backend._tw_latest_result


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


def install() -> None:
    backend._tw_latest_result = _tw_latest_result


install()
