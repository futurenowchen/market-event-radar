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
    source_url = str(row.get("URL") or "").strip()
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
