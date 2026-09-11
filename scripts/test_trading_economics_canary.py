from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_event_radar.providers import trading_economics as te


def main() -> None:
    # Fixture follows the Trading Economics point-in-time documentation shape.
    row = {
        "CalendarId": "87213",
        "Date": "2016-12-01T13:30:00",
        "Country": "United States",
        "Category": "Initial Jobless Claims",
        "Event": "Initial Jobless Claims",
        "Reference": "Nov/26",
        "Source": "U.S. Department of Labor",
        "Actual": "268K",
        "Previous": "251K",
        "Forecast": "253K",
        "TEForecast": "253.1K",
        "URL": "/united-states/jobless-claims",
        "Unit": "K",
        "Ticker": "IJCUSA",
    }
    release = datetime(2016, 12, 1, 13, 30, tzinfo=timezone.utc)

    parsed = te.parse_provider_datetime(row["Date"])
    assert parsed == release

    match = te.select_matching_row(
        [row],
        indicator="Initial Jobless Claims",
        release_time=release,
    )
    assert match is not None
    assert match["CalendarId"] == "87213"

    # Wrong indicator or materially shifted release time must not match.
    assert te.select_matching_row(
        [row],
        indicator="Unemployment Rate",
        release_time=release,
    ) is None
    assert te.select_matching_row(
        [row],
        indicator="Initial Jobless Claims",
        release_time=datetime(2016, 12, 1, 14, 0, tzinfo=timezone.utc),
    ) is None

    observation = te.observation_from_row(
        row,
        event_key="claims",
        event_family="claims",
        metric_id="initial_claims",
        release_time=datetime(2016, 12, 1, 14, 0, tzinfo=timezone.utc),
        fetched_at=datetime(2016, 12, 1, 13, 0, tzinfo=timezone.utc),
    )
    assert observation is not None
    assert observation.consensus == "253K"
    assert observation.provider_event_id == "87213"
    assert observation.source_url == "https://tradingeconomics.com/united-states/jobless-claims"
    assert observation.eligible_for_surprise

    print("Trading Economics canary helper tests passed")


if __name__ == "__main__":
    main()
