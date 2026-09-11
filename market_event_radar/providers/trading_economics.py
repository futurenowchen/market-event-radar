from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..consensus import ConsensusObservation


BASE_URL = "https://api.tradingeconomics.com/calendar"
PROVIDER_ID = "trading-economics"
API_KEY_ENV = "TRADING_ECONOMICS_API_KEY"


def configured() -> bool:
    return bool(os.getenv(API_KEY_ENV, "").strip())


def fetch_calendar_rows(*, country: str, indicator: str, start: str, end: str, timeout: float = 10.0) -> list[dict]:
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        return []
    url = (
        f"{BASE_URL}/country/{quote(country)}/indicator/{quote(indicator)}/{quote(start)}/{quote(end)}"
        f"?c={quote(api_key)}&f=json&values=true"
    )
    req = Request(url, headers={"User-Agent": "market-event-radar/consensus-v1"})
    try:
        with urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    return [dict(row) for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


def parse_provider_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    # TE calendar examples expose UTC release times without an explicit offset
    # (for example 13:30 for an 08:30 ET release). Canary matching treats those
    # naive timestamps as UTC and verifies them against our timezone-aware event.
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def select_matching_row(
    rows: list[dict],
    *,
    indicator: str,
    release_time: datetime,
    tolerance_minutes: int = 10,
) -> dict | None:
    if release_time.tzinfo is None:
        raise ValueError("release_time must be timezone-aware")
    expected = release_time.astimezone(timezone.utc)
    indicator_norm = _norm(indicator)
    candidates: list[tuple[float, dict]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        category = _norm(row.get("Category"))
        event = _norm(row.get("Event"))
        if indicator_norm not in {category, event}:
            continue
        row_time = parse_provider_datetime(row.get("Date"))
        if row_time is None:
            continue
        delta_seconds = abs((row_time - expected).total_seconds())
        if delta_seconds <= tolerance_minutes * 60:
            candidates.append((delta_seconds, row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return dict(candidates[0][1])


def observation_from_row(
    row: dict,
    *,
    event_key: str,
    event_family: str,
    metric_id: str,
    release_time: datetime,
    fetched_at: datetime | None = None,
    as_of: datetime | None = None,
) -> ConsensusObservation | None:
    """Normalize TE's survey Forecast, never TEForecast, into our consensus contract."""
    raw = str(row.get("Forecast") or "").strip()
    if not raw:
        numeric = row.get("ForecastValue")
        if numeric not in (None, ""):
            unit = str(row.get("Unit") or "").strip()
            raw = f"{numeric}{unit}" if unit in {"%", "K", "M"} else str(numeric)
    if not raw:
        return None

    fetched_at = fetched_at or datetime.now(timezone.utc)
    source_url = str(row.get("URL") or row.get("SourceURL") or "").strip()
    if source_url.startswith("/"):
        source_url = "https://tradingeconomics.com" + source_url

    return ConsensusObservation(
        event_key=event_key,
        event_family=event_family,
        metric_id=metric_id,
        consensus=raw,
        provider=PROVIDER_ID,
        provider_event_id=str(row.get("CalendarId") or row.get("Ticker") or row.get("Symbol") or ""),
        fetched_at=fetched_at,
        as_of=as_of,
        release_time=release_time,
        unit=str(row.get("Unit") or ""),
        source_url=source_url,
        raw_value=str(row.get("Forecast") or row.get("ForecastValue") or ""),
    )
