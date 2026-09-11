from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_event_radar.consensus_mapping import target_for
from market_event_radar.providers import trading_economics as te


def _load_snapshot(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("snapshot root must be an object")
    return payload


def _iter_queries(payload: dict):
    for event in payload.get("events", []):
        if not isinstance(event, dict):
            continue
        provider = str(event.get("provider") or "").strip()
        event_id = str(event.get("event_id") or "").strip()
        try:
            release_time = datetime.fromisoformat(str(event.get("time_tpe") or ""))
        except ValueError:
            continue
        if release_time.tzinfo is None:
            continue
        metrics = event.get("metrics") or []
        if not isinstance(metrics, list):
            continue
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            metric_id = str(metric.get("metric_id") or "").strip()
            target = target_for(provider, metric_id)
            if target is None:
                continue
            yield event, metric, target, event_id, release_time


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Trading Economics consensus mappings without mutating production snapshots."
    )
    parser.add_argument("--snapshot", default="data/latest.json")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--require-key",
        action="store_true",
        help="Exit non-zero instead of dry-running when TRADING_ECONOMICS_API_KEY is absent.",
    )
    args = parser.parse_args()

    payload = _load_snapshot(Path(args.snapshot))
    queries = list(_iter_queries(payload))[: max(args.limit, 0)]
    configured = te.configured()

    if not configured:
        plan = [
            {
                "event_id": event_id,
                "provider": str(event.get("provider") or ""),
                "metric_id": str(metric.get("metric_id") or ""),
                "event_family": target.event_family,
                "te_indicator": target.trading_economics_indicator,
                "release_time": release_time.isoformat(),
            }
            for event, metric, target, event_id, release_time in queries
        ]
        print(json.dumps({"mode": "dry-run", "query_count": len(plan), "queries": plan}, ensure_ascii=False, indent=2))
        if args.require_key:
            print("TRADING_ECONOMICS_API_KEY is required for live canary", file=sys.stderr)
            return 2
        return 0

    fetched_at = datetime.now(timezone.utc)
    results: list[dict] = []
    cache: dict[tuple[str, str, str], list[dict]] = {}
    failures = 0

    for event, metric, target, event_id, release_time in queries:
        day = release_time.astimezone(timezone.utc).date().isoformat()
        cache_key = (target.country, target.trading_economics_indicator, day)
        if cache_key not in cache:
            cache[cache_key] = te.fetch_calendar_rows(
                country=target.country,
                indicator=target.trading_economics_indicator,
                start=day,
                end=day,
            )
        rows = cache[cache_key]
        row = te.select_matching_row(
            rows,
            indicator=target.trading_economics_indicator,
            release_time=release_time,
        )
        if row is None:
            failures += 1
            results.append(
                {
                    "event_id": event_id,
                    "metric_id": target.metric_id,
                    "event_family": target.event_family,
                    "te_indicator": target.trading_economics_indicator,
                    "status": "NO_MATCH",
                    "row_count": len(rows),
                }
            )
            continue

        observation = te.observation_from_row(
            row,
            event_key=event_id,
            event_family=target.event_family,
            metric_id=target.metric_id,
            release_time=release_time,
            fetched_at=fetched_at,
        )
        results.append(
            {
                "event_id": event_id,
                "metric_id": target.metric_id,
                "event_family": target.event_family,
                "te_indicator": target.trading_economics_indicator,
                "status": "MATCHED" if observation else "MATCHED_NO_CONSENSUS",
                "calendar_id": str(row.get("CalendarId") or ""),
                "ticker": str(row.get("Ticker") or row.get("Symbol") or ""),
                "te_date": str(row.get("Date") or ""),
                "unit": str(row.get("Unit") or ""),
                "forecast": str(row.get("Forecast") or ""),
                "te_forecast_present": bool(str(row.get("TEForecast") or "").strip()),
                "eligible_for_surprise_now": bool(observation and observation.eligible_for_surprise),
            }
        )

    print(
        json.dumps(
            {
                "mode": "live-canary",
                "snapshot": args.snapshot,
                "query_count": len(queries),
                "unique_api_queries": len(cache),
                "failures": failures,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
