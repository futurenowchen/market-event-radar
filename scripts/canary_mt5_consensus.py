from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_event_radar.providers.mt5_calendar import (
    iter_candidate_observations,
    load_export,
    release_time_utc,
    target_key_for_row,
    validate_export,
)

OFFICIAL_PROVIDER_BY_FAMILY = {
    "cpi": "official-us-bls-cpi",
    "ppi": "official-us-bls-ppi",
    "claims": "official-us-dol-claims",
}


def _parse_iso(value: object) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def _load_snapshot(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("snapshot root must be an object")
    return payload


def _match_snapshot_event(snapshot: dict, family: str, release_time: datetime, tolerance_minutes: int = 15) -> dict | None:
    provider = OFFICIAL_PROVIDER_BY_FAMILY.get(family)
    if not provider:
        return None
    candidates: list[tuple[float, dict]] = []
    for event in snapshot.get("events", []):
        if not isinstance(event, dict) or str(event.get("provider") or "") != provider:
            continue
        event_time = _parse_iso(event.get("time_tpe"))
        if event_time is None:
            continue
        delta = abs((event_time - release_time).total_seconds())
        if delta <= tolerance_minutes * 60:
            candidates.append((delta, event))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _metric_from_event(event: dict, metric_id: str) -> dict | None:
    for metric in event.get("metrics", []):
        if isinstance(metric, dict) and str(metric.get("metric_id") or "") == metric_id:
            return metric
    return None


def build_report(export_payload: dict, snapshot: dict) -> dict:
    validate_export(export_payload)
    observations = list(iter_candidate_observations(export_payload))
    results: list[dict] = []

    for observation in observations:
        event = _match_snapshot_event(snapshot, observation.event_family, observation.release_time)
        metric = _metric_from_event(event, observation.metric_id) if event else None
        status = "MATCHED" if event and metric else "NO_OFFICIAL_MATCH"
        results.append(
            {
                **observation.to_dict(),
                "status": status,
                "official_event_id": str(event.get("event_id") or "") if event else "",
                "official_provider": str(event.get("provider") or "") if event else "",
                "official_metric_label": str(metric.get("label") or "") if metric else "",
                "official_previous": str(metric.get("previous") or "") if metric else "",
                "official_unit": str(metric.get("unit") or "") if metric else "",
            }
        )

    unmatched_provider_rows: list[dict] = []
    for row in export_payload.get("rows", []):
        if not isinstance(row, dict) or target_key_for_row(row) is not None:
            continue
        unmatched_provider_rows.append(
            {
                "provider_event_id": str(row.get("provider_event_id") or ""),
                "provider_value_id": str(row.get("provider_value_id") or ""),
                "event_code": str(row.get("event_code") or ""),
                "event_name": str(row.get("event_name") or ""),
                "release_time": release_time_utc(export_payload, row).isoformat(),
                "forecast": row.get("forecast"),
                "unit": str(row.get("unit") or ""),
                "multiplier": str(row.get("multiplier") or ""),
            }
        )

    matched = sum(item["status"] == "MATCHED" for item in results)
    pre_release = sum(item["status"] == "MATCHED" and item["captured_before_release"] for item in results)
    return {
        "mode": "mt5-private-canary",
        "provider": export_payload.get("provider"),
        "terminal_language": export_payload.get("terminal_language"),
        "capture_time_gmt": export_payload.get("capture_time_gmt"),
        "server_utc_offset_seconds": export_payload.get("server_utc_offset_seconds"),
        "candidate_observation_count": len(results),
        "matched_official_count": matched,
        "pre_release_match_count": pre_release,
        "promotion_status": "NOT_PROMOTED",
        "promotion_reason": "MT5 forecast remains provider_forecast until repeated cross-source consensus equivalence is verified.",
        "results": results,
        "unmatched_provider_rows": unmatched_provider_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a private/local MetaTrader 5 Economic Calendar export without mutating the public snapshot."
    )
    parser.add_argument("--export", required=True, help="Path to MT5 private/local JSON export")
    parser.add_argument("--snapshot", default="data/latest.json", help="Official public snapshot used only for identity matching")
    parser.add_argument("--output", help="Optional local evidence JSON path; omit to print only")
    parser.add_argument("--require-pre-release", action="store_true", help="Return non-zero unless at least one matched forecast was captured before release")
    args = parser.parse_args()

    export_payload = load_export(args.export)
    snapshot = _load_snapshot(Path(args.snapshot))
    report = build_report(export_payload, snapshot)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")

    if report["matched_official_count"] == 0:
        return 1
    if args.require_pre_release and report["pre_release_match_count"] == 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
