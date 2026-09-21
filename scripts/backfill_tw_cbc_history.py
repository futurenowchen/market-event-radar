from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as official
import v2_event_official_asia  # noqa: F401
import v2_event_official_taiwan  # noqa: F401
import v2_event_official_resilience  # noqa: F401
import v2_event_official_taiwan_resilience  # noqa: F401
import v2_event_official_us_high_signal  # noqa: F401
import v2_event_official_us_phase2  # noqa: F401
import v2_event_official_us_claims  # noqa: F401
import v2_event_official_us_phase3  # noqa: F401
import v2_event_official_us_phase4  # noqa: F401
import v2_event_official_us_phase4_resilience  # noqa: F401
import v2_event_official_release_resilience  # noqa: F401
import v2_event_official_previous_resilience  # noqa: F401
import v2_event_company_ir  # noqa: F401
import v2_event_semantics  # noqa: F401
import v2_event_radar as er

from scripts.update_event_history import update_history
from scripts.update_event_radar_snapshot import event_to_json


def resolve_event(meeting_day: date):
    start = datetime.combine(meeting_day, datetime.min.time(), tzinfo=er.TPE)
    end = start + timedelta(days=1)
    official.clear_event_caches()
    events, ok = official._tw_cbc_events(start, end, f"cbc-backfill-{meeting_day.isoformat()}")
    if not ok:
        raise RuntimeError("CBC official collector reported unhealthy")
    event_id = f"official-tw-cbc-{meeting_day.isoformat()}"
    event = next((row for row in events if row.event_id == event_id), None)
    if event is None:
        raise RuntimeError(f"CBC event not found: {event_id}")
    if not event.actual:
        raise RuntimeError(f"CBC Actual is blank for {event_id}")
    if not event.previous:
        raise RuntimeError(f"CBC Previous is blank for {event_id}")
    return event


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill one Taiwan CBC released event into the append-only history ledger.")
    parser.add_argument("--date", required=True, help="Meeting date in YYYY-MM-DD")
    parser.add_argument("--history-dir", default="data/history")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    meeting_day = date.fromisoformat(args.date)
    event = resolve_event(meeting_day)
    row = event_to_json(event)

    print(
        f"Resolved {event.event_id}: actual={event.actual}, "
        f"previous={event.previous}, source={event.source_url}"
    )

    if args.dry_run:
        return

    payload = {
        "schema_version": 2,
        "generated_at_tpe": datetime.now(er.TPE).isoformat(),
        "events": [row],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False)
        temp_path = Path(handle.name)

    try:
        path, count = update_history(temp_path, Path(args.history_dir))
    finally:
        temp_path.unlink(missing_ok=True)

    print(f"History backfill: appended {count} record(s) to {path}")


if __name__ == "__main__":
    main()
