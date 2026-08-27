from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

MEANINGFUL_FIELDS = (
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
)

REGION_SOURCE_GROUPS = {
    "US": ("us_bls", "us_bea", "us_fed"),
    "TW": ("tw_dgbas", "tw_cbc"),
    "JP": ("jp_stat", "jp_esri", "jp_boj"),
    "KR": ("kr_mods", "kr_bok"),
}


def _canonical_event(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in MEANINGFUL_FIELDS}


def _fingerprint(row: dict[str, Any]) -> str:
    raw = json.dumps(_canonical_event(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _parse_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else None


def _load_snapshot(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"snapshot missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"snapshot is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("snapshot root must be a JSON object")
    return payload


def _load_history(history_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    files = sorted(history_dir.glob("**/*.jsonl"))
    if not files:
        return [], [f"no history JSONL files found under {history_dir}"]

    for path in files:
        for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid history JSON: {path}:{line_no}: {exc}")
                continue
            if not isinstance(row, dict):
                errors.append(f"history row is not an object: {path}:{line_no}")
                continue
            records.append(row)
    return records, errors


def _latest_history(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    latest_seen: dict[str, datetime] = {}
    for row in records:
        event_id = str(row.get("event_id") or "").strip()
        observed_at = _parse_datetime(row.get("observed_at_tpe"))
        if not event_id or observed_at is None:
            continue
        if event_id not in latest_seen or observed_at >= latest_seen[event_id]:
            latest[event_id] = row
            latest_seen[event_id] = observed_at
    return latest


def _check_source_health(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if payload.get("official_macro_ready") is not True:
        issues.append("official_macro_ready is not true")

    health = payload.get("source_health")
    if not isinstance(health, dict):
        issues.append("source_health is missing or invalid")
        return issues

    for region, keys in REGION_SOURCE_GROUPS.items():
        if not any(bool(health.get(key)) for key in keys):
            issues.append(f"{region} official-source group has no healthy provider")
    return issues


def check_health(
    snapshot_path: Path,
    history_dir: Path,
    *,
    now: datetime,
    max_snapshot_age_hours: float,
    result_grace_minutes: int,
    released_retention_hours: int,
) -> list[str]:
    issues: list[str] = []
    payload = _load_snapshot(snapshot_path)

    if int(payload.get("schema_version") or 0) < 2:
        issues.append("snapshot schema_version is below 2")

    generated_at = _parse_datetime(payload.get("generated_at_tpe"))
    if generated_at is None:
        issues.append("generated_at_tpe is missing or not timezone-aware")
    else:
        age = now.astimezone(generated_at.tzinfo) - generated_at
        if age > timedelta(hours=max_snapshot_age_hours):
            issues.append(
                f"snapshot is stale: age={age.total_seconds() / 3600:.1f}h "
                f"> {max_snapshot_age_hours:g}h"
            )

    issues.extend(_check_source_health(payload))

    events = payload.get("events")
    if not isinstance(events, list) or not events:
        issues.append("snapshot contains no events")
        events = []

    history_records, history_errors = _load_history(history_dir)
    issues.extend(history_errors)
    latest_history = _latest_history(history_records)
    if not latest_history:
        issues.append("history ledger contains no usable event states")

    snapshot_by_id: dict[str, dict[str, Any]] = {}
    for row in events:
        if not isinstance(row, dict):
            issues.append("snapshot contains a non-object event row")
            continue
        event_id = str(row.get("event_id") or "").strip()
        if not event_id:
            issues.append("snapshot contains an event without event_id")
            continue
        snapshot_by_id[event_id] = row

        history_row = latest_history.get(event_id)
        if history_row is None:
            issues.append(f"snapshot event missing from history ledger: {event_id}")
        else:
            expected = _fingerprint(row)
            observed = str(history_row.get("fingerprint") or "")
            if observed != expected:
                issues.append(
                    f"snapshot/history mismatch for {event_id}: "
                    f"snapshot={expected}, history={observed or 'missing'}"
                )

        event_time = _parse_datetime(row.get("time_tpe"))
        if event_time is None:
            issues.append(f"event has invalid time_tpe: {event_id}")
            continue

        # Consensus forecasts are intentionally not required in official-free-v1.
        # Actual values, however, are expected for released S/A macro and central-bank events.
        category = str(row.get("category") or "")
        should_have_result = (
            bool(row.get("expects_result"))
            and str(row.get("tier") or "") in {"S", "A"}
            and category in {"總體經濟", "央行事件"}
        )
        overdue_at = event_time + timedelta(minutes=result_grace_minutes)
        if should_have_result and not str(row.get("actual") or "").strip() and now >= overdue_at:
            elapsed = now.astimezone(event_time.tzinfo) - event_time
            if elapsed <= timedelta(hours=released_retention_hours):
                issues.append(
                    f"overdue result: {event_id} ({row.get('title')}) has no actual value "
                    f"{elapsed.total_seconds() / 3600:.1f}h after release time"
                )

    # A released event must stay in the live snapshot during the configured retention window.
    # This catches the class of bug where daily refreshes silently drop yesterday's releases.
    for event_id, history_row in latest_history.items():
        event = history_row.get("event")
        if not isinstance(event, dict) or not str(event.get("actual") or "").strip():
            continue
        event_time = _parse_datetime(event.get("time_tpe"))
        if event_time is None:
            continue
        elapsed = now.astimezone(event_time.tzinfo) - event_time
        if timedelta(0) <= elapsed <= timedelta(hours=released_retention_hours):
            if event_id not in snapshot_by_id:
                issues.append(
                    f"recent released event disappeared from snapshot: {event_id} "
                    f"({elapsed.total_seconds() / 3600:.1f}h old)"
                )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only health watchdog for the market-event-radar data chain.")
    parser.add_argument("--snapshot", default="data/latest.json")
    parser.add_argument("--history-dir", default="data/history")
    parser.add_argument("--max-snapshot-age-hours", type=float, default=30.0)
    parser.add_argument("--result-grace-minutes", type=int, default=90)
    parser.add_argument("--released-retention-hours", type=int, default=48)
    parser.add_argument(
        "--now",
        default="",
        help="Optional timezone-aware ISO timestamp for deterministic tests/manual checks.",
    )
    args = parser.parse_args()

    now = _parse_datetime(args.now) if args.now else datetime.now().astimezone()
    if now is None:
        print("RADAR WATCHDOG FAIL")
        print("- --now must be a timezone-aware ISO timestamp")
        return 2

    try:
        issues = check_health(
            Path(args.snapshot),
            Path(args.history_dir),
            now=now,
            max_snapshot_age_hours=args.max_snapshot_age_hours,
            result_grace_minutes=args.result_grace_minutes,
            released_retention_hours=args.released_retention_hours,
        )
    except Exception as exc:
        print("RADAR WATCHDOG FAIL")
        print(f"- watchdog could not complete: {exc}")
        return 2

    if issues:
        print("RADAR WATCHDOG FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("RADAR WATCHDOG PASS")
    print("- snapshot freshness: OK")
    print("- official source health: OK")
    print("- snapshot/history consistency: OK")
    print("- released-event retention: OK")
    print("- overdue S/A macro results: none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
