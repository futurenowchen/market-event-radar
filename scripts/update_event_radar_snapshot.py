from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as official
import v2_event_official_asia  # noqa: F401  # installs hardened JP schedule parsers
import v2_event_official_taiwan  # noqa: F401  # installs hardened TW schedules
import v2_event_official_resilience  # noqa: F401  # installs resilient BLS/KR schedules
import v2_event_company_ir  # noqa: F401  # installs official company IR fallbacks
import v2_event_radar as er


def event_to_json(event: er.MarketEvent) -> dict:
    row = asdict(event)
    row["time_tpe"] = event.time_tpe.isoformat()
    row["market_tags"] = list(event.market_tags)
    return row


def event_from_json(row: dict) -> er.MarketEvent | None:
    try:
        dt = datetime.fromisoformat(str(row.get("time_tpe") or "")).astimezone(er.TPE)
    except Exception:
        return None
    return er.MarketEvent(
        event_id=str(row.get("event_id") or ""),
        time_tpe=dt,
        title=str(row.get("title") or ""),
        category=str(row.get("category") or ""),
        importance=int(row.get("importance") or 1),
        tier=str(row.get("tier") or "B"),
        country=str(row.get("country") or ""),
        market_tags=tuple(row.get("market_tags") or ()),
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


def load_existing(path: Path) -> tuple[dict, list[er.MarketEvent]]:
    if not path.exists():
        return {}, []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, []
    events = []
    for row in payload.get("events", []):
        event = event_from_json(row)
        if event is not None:
            events.append(event)
    return payload, events


def events_signature(events: list[er.MarketEvent]) -> str:
    rows = [event_to_json(e) for e in sorted(events, key=lambda x: (x.time_tpe, x.event_id))]
    return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_daily(now: datetime) -> tuple[list[er.MarketEvent], dict[str, bool], bool]:
    official.clear_event_caches()
    radar = official.load_event_radar(7)
    raw = list(radar.raw_events)
    health = dict(getattr(radar, "source_health", {}))
    ready = bool(getattr(radar, "official_macro_ready", False))
    return raw, health, ready


def build_smart(existing: list[er.MarketEvent], now: datetime) -> list[er.MarketEvent]:
    if not existing:
        return build_daily(now)[0]
    official.clear_event_caches()
    return official.smart_refresh_missing(existing, now)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("daily", "smart"), required=True)
    parser.add_argument("--snapshot", required=True)
    args = parser.parse_args()

    now = datetime.now(er.TPE)
    path = Path(args.snapshot)
    existing_payload, existing = load_existing(path)

    if args.mode == "daily":
        events, source_health, official_macro_ready = build_daily(now)
        if not official_macro_ready:
            failed = ", ".join(name for name, ok in sorted(source_health.items()) if not ok) or "unknown"
            print(f"Official macro sources incomplete ({failed}); preserving previous snapshot for unattended retry.")
            return
    else:
        events = build_smart(existing, now)
        source_health = dict(existing_payload.get("source_health") or {})
        official_macro_ready = bool(existing_payload.get("official_macro_ready"))

    events = [e for e in er._dedupe(events) if now - timedelta(hours=12) <= e.time_tpe <= now + timedelta(days=7)]

    if args.mode == "smart" and events_signature(events) == events_signature(existing):
        print("No provider values changed; snapshot left untouched.")
        return

    provider_counts = Counter(e.provider for e in events)
    payload = {
        "schema_version": 2,
        "snapshot_date_tpe": now.date().isoformat(),
        "generated_at_tpe": now.isoformat(),
        "update_mode": args.mode,
        "macro_backend": "official-free-v1",
        "official_macro_ready": official_macro_ready,
        "event_count": len(events),
        "source_health": dict(sorted(source_health.items())),
        "provider_counts": dict(sorted(provider_counts.items())),
        "events": [event_to_json(e) for e in events],
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(events)} events to {path} (mode={args.mode}, official_macro_ready={'yes' if official_macro_ready else 'no'}).")


if __name__ == "__main__":
    main()
