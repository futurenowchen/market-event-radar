from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

TPE = timezone(timedelta(hours=8))


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TPE)
    return dt.astimezone(TPE)


def emit(mode: str, reason: str) -> None:
    print(f"refresh_mode={mode}")
    print(f"reason={reason}")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"mode={mode}\n")
            handle.write(f"reason={reason}\n")


def decide(snapshot: Path, force_daily: bool, now: datetime | None = None) -> tuple[str, str]:
    now = now or datetime.now(TPE)
    if force_daily:
        return "daily", "manual force"
    if not snapshot.exists():
        return "daily", "snapshot missing"
    try:
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
    except Exception:
        return "daily", "snapshot unreadable"

    try:
        schema_version = int(payload.get("schema_version") or 0)
    except (TypeError, ValueError):
        schema_version = 0
    if schema_version < 2:
        return "daily", "snapshot schema needs migration"
    if str(payload.get("snapshot_date_tpe") or "").strip() != now.date().isoformat():
        return "daily", "new Taiwan calendar day"
    if payload.get("official_macro_ready") is not True:
        return "daily", "official macro snapshot incomplete"

    due = []
    for event in payload.get("events", []):
        if not event.get("expects_result") or str(event.get("actual") or "").strip():
            continue
        event_time = parse_time(str(event.get("time_tpe") or ""))
        if event_time is None:
            continue
        if now >= event_time + timedelta(minutes=5) and now - event_time <= timedelta(hours=12):
            due.append(event)
    if due:
        labels = ", ".join(str(e.get("title") or e.get("event_id") or "event") for e in due[:3])
        return "smart", f"{len(due)} released event(s) still missing actual value: {labels}"
    return "none", "snapshot current and no released result is missing"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="data/latest.json")
    parser.add_argument("--force-daily", default="false")
    args = parser.parse_args()
    mode, reason = decide(Path(args.snapshot), parse_bool(args.force_daily))
    emit(mode, reason)


if __name__ == "__main__":
    main()
