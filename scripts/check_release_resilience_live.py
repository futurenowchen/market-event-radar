from __future__ import annotations

import sys
from datetime import date, datetime
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

    # Exercise the real post-release fallback path, not just the widget parser.
    retail_event = backend._event(
        event_id="official-us-census-retail-2026-09-16",
        dt=datetime.fromisoformat("2026-09-16T20:30:00+08:00"),
        title="美國零售銷售（Retail Sales）",
        country="美國",
        tier="A",
        tags=("美國", "零售銷售"),
        source="U.S. Census Bureau",
        source_url="https://www.census.gov/retail/sales.html",
        provider="official-us-census-retail",
    )
    object.__setattr__(retail_event, "reference_month", date(2026, 8, 1))
    metrics = resilience._retail_metrics_resilient(
        retail_event,
        datetime.now(backend.TPE),
        "release-resilience-integrated",
    )
    primary = next((row for row in metrics if row.get("is_primary")), None)
    if not primary or not primary.get("actual"):
        raise SystemExit(f"Integrated Census retail fallback returned no primary actual: {metrics}")
    print(f"Integrated Census retail actual: {primary['actual']}")

    print("Release resilience live probe passed")


if __name__ == "__main__":
    main()
