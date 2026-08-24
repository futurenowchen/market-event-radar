from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

REQUIRED_TOP_LEVEL = {
    "schema_version",
    "snapshot_date_tpe",
    "generated_at_tpe",
    "update_mode",
    "official_macro_ready",
    "event_count",
    "events",
}

REQUIRED_EVENT = {
    "event_id",
    "time_tpe",
    "title",
    "category",
    "importance",
    "tier",
    "country",
    "market_tags",
    "actual",
    "forecast",
    "previous",
    "source",
    "source_url",
    "status",
    "expects_result",
    "provider",
    "symbol",
}


def fail(message: str) -> None:
    raise SystemExit(f"snapshot validation failed: {message}")


def parse_dt(value: object, field: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        fail(f"{field} is not ISO-8601: {value!r}")
        raise exc


def validate(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_TOP_LEVEL - payload.keys()
    if missing:
        fail(f"missing top-level fields: {sorted(missing)}")
    if payload["schema_version"] != 2:
        fail(f"unsupported schema_version={payload['schema_version']!r}")
    if payload["update_mode"] not in {"daily", "smart"}:
        fail(f"invalid update_mode={payload['update_mode']!r}")
    parse_dt(payload["generated_at_tpe"], "generated_at_tpe")

    events = payload["events"]
    if not isinstance(events, list):
        fail("events must be an array")
    if payload["event_count"] != len(events):
        fail(f"event_count={payload['event_count']} but len(events)={len(events)}")

    seen: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            fail(f"events[{index}] must be an object")
        missing_event = REQUIRED_EVENT - event.keys()
        if missing_event:
            fail(f"events[{index}] missing fields: {sorted(missing_event)}")
        event_id = str(event["event_id"])
        if not event_id:
            fail(f"events[{index}].event_id is empty")
        if event_id in seen:
            fail(f"duplicate event_id={event_id}")
        seen.add(event_id)
        parse_dt(event["time_tpe"], f"events[{index}].time_tpe")
        if event["tier"] not in {"S", "A", "B"}:
            fail(f"events[{index}].tier={event['tier']!r}")
        if not isinstance(event["market_tags"], list):
            fail(f"events[{index}].market_tags must be an array")
        if not isinstance(event["expects_result"], bool):
            fail(f"events[{index}].expects_result must be boolean")

    print(f"OK: {path} contains {len(events)} valid events (schema v2).")


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/latest.json")
    validate(path)


if __name__ == "__main__":
    main()
