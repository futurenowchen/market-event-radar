from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as backend
import v2_event_official_release_resilience as resilience


def main() -> None:
    calendar = """
    2026 FOMC Meetings
    January 27-28
    Minutes Released February 18, 2026
    March 17–18*
    Minutes Released April 8, 2026
    September 15-16*
    Minutes Released October 7, 2026
    December 8-9
    2027 FOMC Meetings
    January 26-27
    """
    assert resilience.parse_fomc_meeting_days(calendar, 2026) == [
        date(2026, 1, 28),
        date(2026, 3, 18),
        date(2026, 9, 16),
        date(2026, 12, 9),
    ]

    fraction_statement = (
        "The Committee decided to lower the target range for the federal funds rate "
        "by 1/4 percentage point to 3-3/4 to 4 percent."
    )
    assert resilience.parse_fed_target_range(fraction_statement) == "3.75–4%"
    decimal_statement = (
        "The Committee decided to maintain the target range for the federal funds rate "
        "at 4.25 to 4.5 percent."
    )
    assert resilience.parse_fed_target_range(decimal_statement) == "4.25–4.5%"

    widget = """
    <section>
      <h3>Advance Monthly Retail Sales</h3>
      <div>August 2026 Report Released September 16th, 2026</div>
      <div>$773.9 B</div>
      <div>+ 0.6 %</div>
    </section>
    """
    ref, values = resilience.parse_census_retail_widget(widget)
    assert ref == date(2026, 8, 1)
    assert values["sales_level"] == "$773.9B"
    assert values["headline_mom"] == "0.6%"

    now = datetime.fromisoformat("2026-09-17T12:00:00+08:00")
    event = backend._event(
        event_id="test-overdue",
        dt=now - timedelta(hours=20),
        title="overdue",
        country="美國",
        tier="A",
        tags=("test",),
        source="test",
        source_url="https://example.com",
        provider="official-test",
    )
    # The old 12h gate made this result permanently unrecoverable even though the
    # public snapshot retained releases for 48h. The new worker must still retry.
    original_collect = backend.collect_official_macro
    try:
        calls = []

        def fake_collect(start, end, token):
            calls.append((start, end, token))
            released = backend._event(
                event_id="test-overdue",
                dt=event.time_tpe,
                title="overdue",
                country="美國",
                tier="A",
                tags=("test",),
                source="test",
                source_url="https://example.com",
                provider="official-test",
                actual="1.0%",
            )
            return [released], {"us_test": True}

        backend.collect_official_macro = fake_collect
        refreshed = resilience._smart_refresh_missing_resilient([event], now)
        assert calls, "20h-old missing result was not retried"
        matching = [row for row in refreshed if row.event_id == "test-overdue"]
        assert matching and matching[-1].actual == "1.0%"
        assert calls[0][0] <= now - timedelta(hours=47, minutes=59)
    finally:
        backend.collect_official_macro = original_collect

    print("Release resilience tests passed")


if __name__ == "__main__":
    main()
