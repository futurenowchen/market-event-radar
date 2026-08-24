from __future__ import annotations

import argparse
import hashlib
import json
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


def _canonical_event(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in MEANINGFUL_FIELDS}


def _fingerprint(row: dict[str, Any]) -> str:
    raw = json.dumps(_canonical_event(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _candidate_history_files(history_dir: Path, observed_at: datetime) -> list[Path]:
    previous_month = (observed_at.replace(day=1) - timedelta(days=1)).strftime("%Y/%m.jsonl")
    current_month = observed_at.strftime("%Y/%m.jsonl")
    return [history_dir / previous_month, history_dir / current_month]


def _latest_states(history_dir: Path, observed_at: datetime) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for path in _candidate_history_files(history_dir, observed_at):
        for row in _load_jsonl(path):
            event_id = str(row.get("event_id") or "")
            if event_id:
                latest[event_id] = row
    return latest


def _change_type(previous: dict[str, Any] | None, current: dict[str, Any]) -> str:
    if previous is None:
        return "first_seen"

    before = previous.get("event") or {}
    after = _canonical_event(current)

    if not before.get("actual") and after.get("actual"):
        return "released"
    if before.get("actual") and after.get("actual") and before.get("actual") != after.get("actual"):
        return "revision"
    if before.get("time_tpe") != after.get("time_tpe"):
        return "schedule_changed"
    if before.get("forecast") != after.get("forecast"):
        return "forecast_changed"
    if before.get("previous") != after.get("previous"):
        return "previous_changed"
    if (before.get("source"), before.get("source_url"), before.get("provider")) != (
        after.get("source"), after.get("source_url"), after.get("provider")
    ):
        return "source_changed"
    return "metadata_changed"


def update_history(snapshot_path: Path, history_dir: Path) -> tuple[Path, int]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    observed_at_text = str(payload.get("generated_at_tpe") or "")
    observed_at = datetime.fromisoformat(observed_at_text)
    if observed_at.tzinfo is None:
        raise ValueError("generated_at_tpe must be timezone-aware")

    latest = _latest_states(history_dir, observed_at)
    output_path = history_dir / observed_at.strftime("%Y/%m.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    appended: list[dict[str, Any]] = []
    for event in payload.get("events", []):
        if not isinstance(event, dict):
            continue
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            continue

        fingerprint = _fingerprint(event)
        previous = latest.get(event_id)
        if previous and previous.get("fingerprint") == fingerprint:
            continue

        record = {
            "event_id": event_id,
            "observed_at_tpe": observed_at.isoformat(),
            "change_type": _change_type(previous, event),
            "fingerprint": fingerprint,
            "event": _canonical_event(event),
        }
        appended.append(record)
        latest[event_id] = record

    if appended:
        with output_path.open("a", encoding="utf-8") as handle:
            for row in appended:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    return output_path, len(appended)


def main() -> None:
    parser = argparse.ArgumentParser(description="Append meaningful event-state changes to the research history ledger.")
    parser.add_argument("--snapshot", default="data/latest.json")
    parser.add_argument("--history-dir", default="data/history")
    args = parser.parse_args()

    path, count = update_history(Path(args.snapshot), Path(args.history_dir))
    print(f"History ledger: appended {count} meaningful change(s) to {path}")


if __name__ == "__main__":
    main()
