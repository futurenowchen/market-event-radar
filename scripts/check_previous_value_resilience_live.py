from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as backend
import v2_event_official_previous_resilience as previous


def main() -> None:
    backend.clear_event_caches()
    previous.clear_previous_value_caches()

    calendar = backend._fetch_text(backend.FED_FOMC_URL, "previous-live")
    prior_day = previous._previous_fomc_meeting_day(calendar, date(2026, 9, 16))
    if prior_day != date(2026, 7, 29):
        raise SystemExit(f"Unexpected previous FOMC meeting: {prior_day}")
    prior_target = previous._fomc_target_for_day(prior_day, "previous-live")
    if prior_target != "3.5–3.75%":
        raise SystemExit(f"Unexpected previous FOMC target range: {prior_target}")
    print(f"FOMC previous target: {prior_target} ({prior_day})")

    fomc_rows, ok = previous._us_fomc_events_with_previous(
        datetime.fromisoformat("2026-09-16T00:00:00+08:00"),
        datetime.fromisoformat("2026-09-18T00:00:00+08:00"),
        "previous-live-integrated",
    )
    fomc = next((row for row in fomc_rows if row.event_id == "official-us-fed-fomc-2026-09-16"), None)
    if not ok or fomc is None or not fomc.actual or fomc.previous != prior_target:
        raise SystemExit(f"Integrated FOMC Previous incomplete: {fomc}")
    print(f"Integrated FOMC: actual={fomc.actual}, previous={fomc.previous}")

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
    metrics = previous._retail_metrics_with_previous(
        retail_event,
        datetime.now(backend.TPE),
        "previous-live-retail",
    )
    primary = next((row for row in metrics if row.get("is_primary")), None)
    if not primary or not primary.get("actual") or not primary.get("previous"):
        raise SystemExit(f"Integrated Retail Previous incomplete: {metrics}")
    print(
        "Integrated Retail: "
        f"actual={primary['actual']}, previous={primary['previous']}, source={primary.get('source_series')}"
    )

    print("Previous-value live probe passed")


if __name__ == "__main__":
    main()
