from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as backend
import v2_event_official_taiwan_resilience as tw


def main() -> None:
    backend.clear_event_caches()

    rate_html = backend._fetch_text(tw.CBC_RATE_URL, "tw-cbc-live-rate")
    rate_rows = tw._parse_cbc_rate_rows(rate_html)
    if not rate_rows:
        raise SystemExit("CBC official discount-rate table is empty or unparseable")
    print(f"CBC latest official rate row: {rate_rows[0][0]} {rate_rows[0][1]}")

    start = datetime.fromisoformat("2026-09-17T00:00:00+08:00")
    end = datetime.fromisoformat("2026-09-18T00:00:00+08:00")
    events, ok = backend._tw_cbc_events(start, end, "tw-cbc-live-integrated")
    if not ok:
        raise SystemExit("CBC official collector reported unhealthy")

    event = next(
        (row for row in events if row.event_id == "official-tw-cbc-2026-09-17"),
        None,
    )
    if event is None:
        raise SystemExit(f"CBC 2026-09-17 event missing from collector: {[row.event_id for row in events]}")
    if not event.actual:
        raise SystemExit(f"CBC 2026-09-17 Actual still blank: {event}")
    if not event.previous:
        raise SystemExit(f"CBC 2026-09-17 Previous still blank: {event}")

    print(
        "CBC 2026-09-17 integrated result: "
        f"actual={event.actual}, previous={event.previous}, source={event.source_url}"
    )
    print("Taiwan CBC live resilience probe passed")


if __name__ == "__main__":
    main()
