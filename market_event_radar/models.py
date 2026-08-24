from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MarketEvent:
    event_id: str
    time_tpe: datetime
    title: str
    category: str
    importance: int
    tier: str = "B"
    country: str = ""
    market_tags: tuple[str, ...] = ()
    actual: str = ""
    forecast: str = ""
    previous: str = ""
    source: str = ""
    source_url: str = ""
    status: str = "scheduled"
    expects_result: bool = False
    provider: str = "manual"
    symbol: str = ""

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "MarketEvent":
        dt = datetime.fromisoformat(str(row.get("time_tpe") or ""))
        if dt.tzinfo is None:
            raise ValueError("time_tpe must include a timezone offset")
        return cls(
            event_id=str(row.get("event_id") or ""),
            time_tpe=dt,
            title=str(row.get("title") or ""),
            category=str(row.get("category") or ""),
            importance=int(row.get("importance") or 1),
            tier=str(row.get("tier") or "B"),
            country=str(row.get("country") or ""),
            market_tags=tuple(str(v) for v in (row.get("market_tags") or ())),
            actual=str(row.get("actual") or ""),
            forecast=str(row.get("forecast") or ""),
            previous=str(row.get("previous") or ""),
            source=str(row.get("source") or ""),
            source_url=str(row.get("source_url") or ""),
            status=str(row.get("status") or "scheduled"),
            expects_result=bool(row.get("expects_result")),
            provider=str(row.get("provider") or "manual"),
            symbol=str(row.get("symbol") or ""),
        )


@dataclass(frozen=True)
class RadarSnapshot:
    schema_version: int
    snapshot_date_tpe: str
    generated_at_tpe: str
    update_mode: str
    macro_backend: str
    official_macro_ready: bool
    events: tuple[MarketEvent, ...]
    source_health: dict[str, bool]
    provider_counts: dict[str, int]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RadarSnapshot":
        return cls(
            schema_version=int(payload.get("schema_version") or 0),
            snapshot_date_tpe=str(payload.get("snapshot_date_tpe") or ""),
            generated_at_tpe=str(payload.get("generated_at_tpe") or ""),
            update_mode=str(payload.get("update_mode") or ""),
            macro_backend=str(payload.get("macro_backend") or ""),
            official_macro_ready=bool(payload.get("official_macro_ready")),
            events=tuple(MarketEvent.from_dict(row) for row in payload.get("events", [])),
            source_health={str(k): bool(v) for k, v in dict(payload.get("source_health") or {}).items()},
            provider_counts={str(k): int(v) for k, v in dict(payload.get("provider_counts") or {}).items()},
        )
