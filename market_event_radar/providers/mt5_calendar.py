from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import json

PROVIDER = "metatrader5-economic-calendar"


def _norm(value: object) -> str:
    text = str(value or "").strip().lower()
    for token in ("(ppi)", "(cpi)"):
        text = text.replace(token, token[1:-1])
    text = text.replace("y/y", "yoy").replace("m/m", "mom")
    return " ".join(text.split())


# Intentionally conservative.
# Core PPI is deliberately absent from both mappings because MetaQuotes'
# public description excludes food and energy, while this radar's official BLS
# core PPI series also excludes trade services.
_CODE_TO_KEY: dict[str, tuple[str, str]] = {
    "consumer-price-index-yy": ("cpi", "headline_yoy"),
    "consumer-price-index-mm": ("cpi", "headline_mom"),
    "consumer-price-index-ex-food-energy-yy": ("cpi", "core_yoy"),
    "consumer-price-index-ex-food-energy-mm": ("cpi", "core_mom"),
    "producer-price-index-yy": ("ppi", "headline_yoy"),
    "producer-price-index-mm": ("ppi", "headline_mom"),
    "initial-jobless-claims": ("claims", "initial_claims"),
}

_NAME_TO_KEY: dict[str, tuple[str, str]] = {
    _norm("CPI y/y"): ("cpi", "headline_yoy"),
    _norm("Consumer Price Index CPI y/y"): ("cpi", "headline_yoy"),
    _norm("CPI m/m"): ("cpi", "headline_mom"),
    _norm("Consumer Price Index CPI m/m"): ("cpi", "headline_mom"),
    _norm("Core CPI y/y"): ("cpi", "core_yoy"),
    _norm("Core CPI m/m"): ("cpi", "core_mom"),
    _norm("PPI y/y"): ("ppi", "headline_yoy"),
    _norm("Producer Price Index PPI y/y"): ("ppi", "headline_yoy"),
    _norm("PPI m/m"): ("ppi", "headline_mom"),
    _norm("Producer Price Index PPI m/m"): ("ppi", "headline_mom"),
    _norm("Initial Jobless Claims"): ("claims", "initial_claims"),
    # Localized Chinese names (MetaTrader 5 on zh-TW / zh-CN systems)
    _norm("CPI 年率y/y"): ("cpi", "headline_yoy"),
    _norm("CPI 年率 y/y"): ("cpi", "headline_yoy"),
    _norm("CPI 月率m/m"): ("cpi", "headline_mom"),
    _norm("CPI 月率 m/m"): ("cpi", "headline_mom"),
    _norm("核心CPI年率 y/y"): ("cpi", "core_yoy"),
    _norm("核心CPI年率y/y"): ("cpi", "core_yoy"),
    _norm("核心CPI月率 m/m"): ("cpi", "core_mom"),
    _norm("核心CPI月率m/m"): ("cpi", "core_mom"),
    _norm("生产者物价指数（PPI）年率y/y"): ("ppi", "headline_yoy"),
    _norm("生产者物价指数(PPI)年率 y/y"): ("ppi", "headline_yoy"),
    _norm("PPI 年率y/y"): ("ppi", "headline_yoy"),
    _norm("PPI年率y/y"): ("ppi", "headline_yoy"),
    _norm("PPI月率m/m"): ("ppi", "headline_mom"),
    _norm("PPI 月率m/m"): ("ppi", "headline_mom"),
    _norm("初领失业金人数"): ("claims", "initial_claims"),
}


@dataclass(frozen=True)
class ProviderForecastObservation:
    event_family: str
    metric_id: str
    provider_forecast: str
    provider: str
    provider_event_id: str
    provider_value_id: str
    event_code: str
    event_name: str
    captured_at: datetime
    release_time: datetime
    unit: str = ""
    multiplier: str = ""
    source_url: str = ""
    previous: str = ""
    revised_previous: str = ""
    actual: str = ""
    digits: int = 0

    @property
    def captured_before_release(self) -> bool:
        return bool(self.provider_forecast.strip()) and self.captured_at < self.release_time

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_family": self.event_family,
            "metric_id": self.metric_id,
            "provider_forecast": self.provider_forecast,
            "provider": self.provider,
            "provider_event_id": self.provider_event_id,
            "provider_value_id": self.provider_value_id,
            "event_code": self.event_code,
            "event_name": self.event_name,
            "captured_at": self.captured_at.isoformat(),
            "release_time": self.release_time.isoformat(),
            "unit": self.unit,
            "multiplier": self.multiplier,
            "source_url": self.source_url,
            "previous": self.previous,
            "revised_previous": self.revised_previous,
            "actual": self.actual,
            "digits": self.digits,
            "captured_before_release": self.captured_before_release,
        }


def load_export(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MT5 export root must be an object")
    return payload


def validate_export(payload: dict[str, Any]) -> None:
    if int(payload.get("schema_version", 0)) != 1:
        raise ValueError("unsupported MT5 export schema_version")
    if str(payload.get("provider") or "") != PROVIDER:
        raise ValueError("unexpected MT5 export provider")
    if not str(payload.get("capture_time_gmt") or "").strip():
        raise ValueError("capture_time_gmt is required")
    if not isinstance(payload.get("rows"), list):
        raise ValueError("rows must be an array")


def parse_mt5_datetime(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("datetime value is required")
    # Exporter emits ISO-like seconds without timezone suffix.
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def capture_time_utc(payload: dict[str, Any]) -> datetime:
    dt = parse_mt5_datetime(payload.get("capture_time_gmt"))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def release_time_utc(payload: dict[str, Any], row: dict[str, Any]) -> datetime:
    server_dt = parse_mt5_datetime(row.get("release_time_server"))
    if server_dt.tzinfo is not None:
        return server_dt.astimezone(timezone.utc)
    offset_seconds = int(payload.get("server_utc_offset_seconds", 0))
    return (server_dt - timedelta(seconds=offset_seconds)).replace(tzinfo=timezone.utc)


def target_key_for_row(row: dict[str, Any]) -> tuple[str, str] | None:
    code = str(row.get("event_code") or "").strip().lower()
    if code in _CODE_TO_KEY:
        return _CODE_TO_KEY[code]
    return _NAME_TO_KEY.get(_norm(row.get("event_name")))


def format_provider_value(value: object, *, digits: int | None = None) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    if digits is None:
        text = f"{number:.12f}".rstrip("0").rstrip(".")
        return "0" if text in {"-0", ""} else text
    return f"{number:.{max(0, min(int(digits), 12))}f}"


def observation_from_row(payload: dict[str, Any], row: dict[str, Any]) -> ProviderForecastObservation | None:
    validate_export(payload)
    key = target_key_for_row(row)
    if key is None:
        return None
    forecast = format_provider_value(row.get("forecast"), digits=row.get("digits"))
    if not forecast:
        return None
    event_family, metric_id = key
    return ProviderForecastObservation(
        event_family=event_family,
        metric_id=metric_id,
        provider_forecast=forecast,
        provider=PROVIDER,
        provider_event_id=str(row.get("provider_event_id") or ""),
        provider_value_id=str(row.get("provider_value_id") or ""),
        event_code=str(row.get("event_code") or ""),
        event_name=str(row.get("event_name") or ""),
        captured_at=capture_time_utc(payload),
        release_time=release_time_utc(payload, row),
        unit=str(row.get("unit") or ""),
        multiplier=str(row.get("multiplier") or ""),
        source_url=str(row.get("source_url") or ""),
        previous=format_provider_value(row.get("previous"), digits=row.get("digits")),
        revised_previous=format_provider_value(row.get("revised_previous"), digits=row.get("digits")),
        actual=format_provider_value(row.get("actual"), digits=row.get("digits")),
        digits=int(row.get("digits") or 0),
    )


def iter_candidate_observations(payload: dict[str, Any]):
    validate_export(payload)
    for row in payload.get("rows", []):
        if not isinstance(row, dict):
            continue
        observation = observation_from_row(payload, row)
        if observation is not None:
            yield observation
