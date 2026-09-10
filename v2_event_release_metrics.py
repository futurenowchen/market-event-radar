from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import v2_event_official as backend


# BLS series are first-party public series. We deliberately keep consensus
# forecasts out of this module; official-free-v1 only stores observed/previous
# values unless a separate licensed consensus provider is added later.
BLS_SERIES = {
    "cpi_headline_nsa": "CUUR0000SA0",
    "cpi_headline_sa": "CUSR0000SA0",
    "cpi_core_nsa": "CUUR0000SA0L1E",
    "cpi_core_sa": "CUSR0000SA0L1E",
    "ppi_headline_nsa": "WPUFD4",
    "ppi_headline_sa": "WPSFD4",
    "ppi_core_nsa": "WPUFD49116",
    "ppi_core_sa": "WPSFD49116",
    "nfp_payroll": "CES0000000001",
    "nfp_unemployment": "LNS14000000",
    "nfp_ahe": "CES0500000003",
}


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


def _year_ago(value: date) -> date:
    return date(value.year - 1, value.month, 1)


def _expected_bls_reference_month(event_time: datetime) -> date:
    # CPI, PPI and Employment Situation normally publish the immediately
    # preceding reference month. Anchoring calculations to the expected month
    # prevents a stale API response from being mistaken for a just-released value.
    release_day = event_time.astimezone(backend.NY).date()
    return _previous_month(_month_start(release_day))


def _expected_pce_reference_month(event_time: datetime) -> date:
    release_day = event_time.astimezone(backend.NY).date()
    return _previous_month(_month_start(release_day))


def _obs_map(rows: list[tuple[date, float]]) -> dict[date, float]:
    return {_month_start(day): float(value) for day, value in rows}


def _fmt_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return ""
    return backend._pct(round(value, digits))


def _fmt_k(value: float | None) -> str:
    if value is None:
        return ""
    rounded = int(round(value))
    sign = "+" if rounded > 0 else ""
    return f"{sign}{rounded}K"


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1.0) * 100.0


def _series_value(data: dict[str, list[tuple[date, float]]], series_id: str, month: date) -> float | None:
    return _obs_map(data.get(series_id, [])).get(month)


def _yoy_value(data: dict[str, list[tuple[date, float]]], series_id: str, month: date) -> float | None:
    return _pct_change(
        _series_value(data, series_id, month),
        _series_value(data, series_id, _year_ago(month)),
    )


def _mom_value(data: dict[str, list[tuple[date, float]]], series_id: str, month: date) -> float | None:
    return _pct_change(
        _series_value(data, series_id, month),
        _series_value(data, series_id, _previous_month(month)),
    )


def _delta_value(data: dict[str, list[tuple[date, float]]], series_id: str, month: date) -> float | None:
    current = _series_value(data, series_id, month)
    previous = _series_value(data, series_id, _previous_month(month))
    if current is None or previous is None:
        return None
    return current - previous


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


def _bls_bundle(family: str, event_time: datetime, now: datetime, refresh_token: str) -> list[dict[str, Any]]:
    ref = _expected_bls_reference_month(event_time)
    prev_ref = _previous_month(ref)
    released = now >= event_time

    if family == "cpi":
        ids = [
            BLS_SERIES["cpi_headline_nsa"],
            BLS_SERIES["cpi_headline_sa"],
            BLS_SERIES["cpi_core_nsa"],
            BLS_SERIES["cpi_core_sa"],
        ]
        data = backend._bls_observations(ids, now, refresh_token)
        values = [
            (
                "headline_yoy", "Headline YoY", BLS_SERIES["cpi_headline_nsa"],
                _yoy_value(data, BLS_SERIES["cpi_headline_nsa"], ref),
                _yoy_value(data, BLS_SERIES["cpi_headline_nsa"], prev_ref), True,
            ),
            (
                "headline_mom", "Headline MoM", BLS_SERIES["cpi_headline_sa"],
                _mom_value(data, BLS_SERIES["cpi_headline_sa"], ref),
                _mom_value(data, BLS_SERIES["cpi_headline_sa"], prev_ref), False,
            ),
            (
                "core_yoy", "Core YoY", BLS_SERIES["cpi_core_nsa"],
                _yoy_value(data, BLS_SERIES["cpi_core_nsa"], ref),
                _yoy_value(data, BLS_SERIES["cpi_core_nsa"], prev_ref), False,
            ),
            (
                "core_mom", "Core MoM", BLS_SERIES["cpi_core_sa"],
                _mom_value(data, BLS_SERIES["cpi_core_sa"], ref),
                _mom_value(data, BLS_SERIES["cpi_core_sa"], prev_ref), False,
            ),
        ]
        bundle = [
            _metric(
                metric_id, label,
                actual=_fmt_pct(current) if released else "",
                previous=_fmt_pct(previous),
                unit="%",
                is_primary=is_primary,
                source_series=series_id,
            )
            for metric_id, label, series_id, current, previous, is_primary in values
            if current is not None or previous is not None
        ]
        return bundle

    if family == "ppi":
        ids = [
            BLS_SERIES["ppi_headline_nsa"],
            BLS_SERIES["ppi_headline_sa"],
            BLS_SERIES["ppi_core_nsa"],
            BLS_SERIES["ppi_core_sa"],
        ]
        data = backend._bls_observations(ids, now, refresh_token)
        values = [
            (
                "headline_yoy", "Final Demand YoY", BLS_SERIES["ppi_headline_nsa"],
                _yoy_value(data, BLS_SERIES["ppi_headline_nsa"], ref),
                _yoy_value(data, BLS_SERIES["ppi_headline_nsa"], prev_ref), True,
            ),
            (
                "headline_mom", "Final Demand MoM", BLS_SERIES["ppi_headline_sa"],
                _mom_value(data, BLS_SERIES["ppi_headline_sa"], ref),
                _mom_value(data, BLS_SERIES["ppi_headline_sa"], prev_ref), False,
            ),
            (
                "core_yoy", "Core YoY（除食品/能源/貿易服務）", BLS_SERIES["ppi_core_nsa"],
                _yoy_value(data, BLS_SERIES["ppi_core_nsa"], ref),
                _yoy_value(data, BLS_SERIES["ppi_core_nsa"], prev_ref), False,
            ),
            (
                "core_mom", "Core MoM（除食品/能源/貿易服務）", BLS_SERIES["ppi_core_sa"],
                _mom_value(data, BLS_SERIES["ppi_core_sa"], ref),
                _mom_value(data, BLS_SERIES["ppi_core_sa"], prev_ref), False,
            ),
        ]
        bundle = [
            _metric(
                metric_id, label,
                actual=_fmt_pct(current) if released else "",
                previous=_fmt_pct(previous),
                unit="%",
                is_primary=is_primary,
                source_series=series_id,
            )
            for metric_id, label, series_id, current, previous, is_primary in values
            if current is not None or previous is not None
        ]
        return bundle

    if family == "nfp":
        ids = [
            BLS_SERIES["nfp_payroll"],
            BLS_SERIES["nfp_unemployment"],
            BLS_SERIES["nfp_ahe"],
        ]
        data = backend._bls_observations(ids, now, refresh_token)
        payroll_current = _delta_value(data, BLS_SERIES["nfp_payroll"], ref)
        payroll_previous = _delta_value(data, BLS_SERIES["nfp_payroll"], prev_ref)
        unemp_current = _series_value(data, BLS_SERIES["nfp_unemployment"], ref)
        unemp_previous = _series_value(data, BLS_SERIES["nfp_unemployment"], prev_ref)
        ahe_mom_current = _mom_value(data, BLS_SERIES["nfp_ahe"], ref)
        ahe_mom_previous = _mom_value(data, BLS_SERIES["nfp_ahe"], prev_ref)
        ahe_yoy_current = _yoy_value(data, BLS_SERIES["nfp_ahe"], ref)
        ahe_yoy_previous = _yoy_value(data, BLS_SERIES["nfp_ahe"], prev_ref)
        values = [
            _metric(
                "payroll_change", "非農新增就業",
                actual=_fmt_k(payroll_current) if released else "",
                previous=_fmt_k(payroll_previous),
                unit="K", is_primary=True, source_series=BLS_SERIES["nfp_payroll"],
            ),
            _metric(
                "unemployment_rate", "失業率",
                actual=_fmt_pct(unemp_current) if released else "",
                previous=_fmt_pct(unemp_previous),
                unit="%", source_series=BLS_SERIES["nfp_unemployment"],
            ),
            _metric(
                "avg_hourly_earnings_mom", "平均時薪 MoM",
                actual=_fmt_pct(ahe_mom_current) if released else "",
                previous=_fmt_pct(ahe_mom_previous),
                unit="%", source_series=BLS_SERIES["nfp_ahe"],
            ),
            _metric(
                "avg_hourly_earnings_yoy", "平均時薪 YoY",
                actual=_fmt_pct(ahe_yoy_current) if released else "",
                previous=_fmt_pct(ahe_yoy_previous),
                unit="%", source_series=BLS_SERIES["nfp_ahe"],
            ),
        ]
        return [m for m in values if m["actual"] or m["previous"]]

    return []


def _signed_percent(direction: str, value: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if direction.strip().lower() == "decreased":
        number = -abs(number)
    return backend._pct(number)


def _pce_section(text: str, start_phrase: str, end_phrase: str | None = None) -> str:
    lower = text.lower()
    start = lower.find(start_phrase.lower())
    if start < 0:
        return ""
    if not end_phrase:
        return text[start:]
    end = lower.find(end_phrase.lower(), start + len(start_phrase))
    return text[start:end if end >= 0 else None]


def _pce_value(section: str, *, core: bool) -> str:
    if not section:
        return ""
    if core:
        pattern = (
            r"excluding food and energy,?\s+the PCE price index(?:\s+for\s+[A-Za-z]+)?\s+"
            r"(increased|decreased)\s+([0-9]+(?:\.[0-9]+)?)\s+percent"
        )
    else:
        pattern = (
            r"the PCE price index(?:\s+for\s+[A-Za-z]+)?\s+"
            r"(increased|decreased)\s+([0-9]+(?:\.[0-9]+)?)\s+percent"
        )
    match = re.search(pattern, section, re.I)
    return _signed_percent(match.group(1), match.group(2)) if match else ""


def _pce_values_from_text(text: str) -> dict[str, str]:
    mom = _pce_section(text, "From the preceding month", "From the same month one year ago")
    yoy = _pce_section(text, "From the same month one year ago")
    return {
        "headline_mom": _pce_value(mom, core=False),
        "core_mom": _pce_value(mom, core=True),
        "headline_yoy": _pce_value(yoy, core=False),
        "core_yoy": _pce_value(yoy, core=True),
    }


def _pce_release_month(url: str) -> date | None:
    match = re.search(r"personal-income-and-outlays-([a-z]+)-(20\d{2})", url, re.I)
    if not match:
        return None
    names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    month = names.get(match.group(1).lower())
    return date(int(match.group(2)), month, 1) if month else None


def _previous_pce_url(current_url: str) -> str:
    current = _pce_release_month(current_url)
    if current is None:
        return ""
    previous = _previous_month(current)
    month_names = (
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    )
    return f"https://www.bea.gov/news/{previous.year}/personal-income-and-outlays-{month_names[previous.month - 1]}-{previous.year}"


def _latest_pce_release(refresh_token: str) -> tuple[str, str]:
    listing = backend._fetch_text(backend.BEA_RELEASES_URL, refresh_token)
    if not listing:
        return "", ""
    for text, url in backend._links(listing, backend.BEA_RELEASES_URL):
        if "personal income and outlays" in text.lower():
            return url, backend._plain_text(backend._fetch_text(url, refresh_token))
    return "", ""


def _pce_bundle(event_time: datetime, now: datetime, refresh_token: str) -> list[dict[str, Any]]:
    expected = _expected_pce_reference_month(event_time)
    current_url, current_text = _latest_pce_release(refresh_token)
    current_month = _pce_release_month(current_url)
    if not current_text or current_month is None:
        return []

    current_values = _pce_values_from_text(current_text)
    if current_month == expected:
        actual_values = current_values
        previous_url = _previous_pce_url(current_url)
        previous_text = backend._plain_text(backend._fetch_text(previous_url, refresh_token)) if previous_url else ""
        previous_values = _pce_values_from_text(previous_text)
        released = now >= event_time
    else:
        # Before the next PCE release, the latest official page is the previous
        # reference month. Use it as prior data, never as the new actual.
        actual_values = {}
        previous_values = current_values if current_month == _previous_month(expected) else {}
        released = False

    specs = (
        ("headline_yoy", "Headline YoY", True),
        ("headline_mom", "Headline MoM", False),
        ("core_yoy", "Core PCE YoY", False),
        ("core_mom", "Core PCE MoM", False),
    )
    bundle = []
    for metric_id, label, is_primary in specs:
        actual = actual_values.get(metric_id, "") if released else ""
        previous = previous_values.get(metric_id, "")
        if actual or previous:
            bundle.append(
                _metric(
                    metric_id, label, actual=actual, previous=previous,
                    unit="%", is_primary=is_primary, source_series="BEA PIO release",
                )
            )
    return bundle


def metrics_for_event(event: Any, now: datetime, refresh_token: str) -> list[dict[str, Any]]:
    provider = str(getattr(event, "provider", "") or "")
    if provider == "official-us-bls-cpi":
        return _bls_bundle("cpi", event.time_tpe, now, refresh_token)
    if provider == "official-us-bls-ppi":
        return _bls_bundle("ppi", event.time_tpe, now, refresh_token)
    if provider == "official-us-bls-nfp":
        return _bls_bundle("nfp", event.time_tpe, now, refresh_token)
    if provider == "official-us-bea-pce":
        return _pce_bundle(event.time_tpe, now, refresh_token)
    return []


def primary_values(family: str, event_time: datetime, now: datetime, refresh_token: str) -> tuple[str, str]:
    if family in {"cpi", "ppi", "nfp"}:
        metrics = _bls_bundle(family, event_time, now, refresh_token)
    elif family == "pce":
        metrics = _pce_bundle(event_time, now, refresh_token)
    else:
        return "", ""
    primary = next((row for row in metrics if row.get("is_primary")), None)
    if not primary:
        return "", ""
    return str(primary.get("actual") or ""), str(primary.get("previous") or "")
