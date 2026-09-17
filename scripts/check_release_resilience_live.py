from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as backend
import v2_event_official_release_resilience as resilience


def main() -> None:
    backend.clear_event_caches()

    calendar = backend._fetch_text(backend.FED_FOMC_URL, "release-resilience-live")
    meeting_days = resilience.parse_fomc_meeting_days(calendar, 2026)
    if date(2026, 9, 16) not in meeting_days:
        raise SystemExit(f"Fed calendar parser missed 2026-09-16: {meeting_days}")
    fake_days = {date(2026, 9, day) for day in (17, 18, 20, 21, 22)}
    if fake_days.intersection(meeting_days):
        raise SystemExit(f"Fed calendar parser emitted release-note dates as meetings: {meeting_days}")

    statement_url = f"{backend.FED_PRESS_BASE}20260916a.htm"
    statement = backend._fetch_text(statement_url, "release-resilience-live")
    target = resilience.parse_fed_target_range(statement)
    if not target:
        raise SystemExit("Fed 2026-09-16 statement target range was not parsed")
    print(f"Fed 2026-09-16 target range: {target}")

    widget = backend._fetch_text(resilience.CENSUS_ECON_WIDGET_URL, "release-resilience-live")
    reference, values = resilience.parse_census_retail_widget(widget)
    if reference is None or reference < date(2026, 8, 1):
        raise SystemExit(f"Census retail widget is stale/unparseable: reference={reference}")
    if not values.get("headline_mom"):
        raise SystemExit(f"Census retail widget has no headline MoM: {values}")
    print(f"Census retail widget: reference={reference}, values={values}")

    print("Release resilience live probe passed")


if __name__ == "__main__":
    main()
