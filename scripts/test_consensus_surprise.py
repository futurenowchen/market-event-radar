from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_event_radar.consensus import ConsensusObservation
from market_event_radar.providers import trading_economics as te
from market_event_radar.surprise import evaluate_surprise, parse_numeric


def _observation(
    *,
    event_key: str,
    event_family: str,
    metric_id: str,
    consensus: str,
    fetched_at: datetime,
    release_time: datetime,
) -> ConsensusObservation:
    return ConsensusObservation(
        event_key=event_key,
        event_family=event_family,
        metric_id=metric_id,
        consensus=consensus,
        provider="test-consensus",
        fetched_at=fetched_at,
        release_time=release_time,
    )


def main() -> None:
    release = datetime(2026, 9, 11, 12, 30, tzinfo=timezone.utc)
    before = release - timedelta(minutes=5)
    after = release + timedelta(minutes=5)

    cpi = _observation(
        event_key="official-us-bls-cpi-2026-09-11",
        event_family="cpi",
        metric_id="headline_yoy",
        consensus="3.2%",
        fetched_at=before,
        release_time=release,
    )
    result = evaluate_surprise("headline_yoy", "3.5%", cpi)
    assert result is not None
    assert abs(result.surprise - 0.3) < 1e-9
    assert result.surprise_unit == "ppt"
    assert result.direction == "HOTTER_THAN_EXPECTED"
    assert result.magnitude == "LARGE"
    assert result.policy_implication == "HAWKISH"

    # Regression guard: Retail Sales shares headline_mom with CPI/PPI/PCE but
    # must be interpreted as a growth surprise, not an inflation surprise.
    retail = _observation(
        event_key="official-us-census-retail-2026-09-16",
        event_family="retail_sales",
        metric_id="headline_mom",
        consensus="0.2%",
        fetched_at=before,
        release_time=release,
    )
    retail_result = evaluate_surprise("headline_mom", "0.5%", retail)
    assert retail_result is not None
    assert retail_result.direction == "STRONGER_THAN_EXPECTED"
    assert retail_result.impulse == "growth_up"
    assert retail_result.policy_implication == "HAWKISH"

    claims = _observation(
        event_key="claims",
        event_family="claims",
        metric_id="initial_claims",
        consensus="200K",
        fetched_at=before,
        release_time=release,
    )
    claims_result = evaluate_surprise("initial_claims", "225K", claims)
    assert claims_result is not None
    assert claims_result.surprise == 25.0
    assert claims_result.direction == "WEAKER_THAN_EXPECTED"
    assert claims_result.policy_implication == "DOVISH"

    eci = _observation(
        event_key="eci",
        event_family="eci",
        metric_id="compensation_qoq",
        consensus="0.8%",
        fetched_at=before,
        release_time=release,
    )
    eci_result = evaluate_surprise("compensation_qoq", "1.0%", eci)
    assert eci_result is not None
    assert eci_result.direction == "HOTTER_THAN_EXPECTED"
    assert eci_result.impulse == "wage_pressure_up"

    late = _observation(
        event_key="late",
        event_family="cpi",
        metric_id="headline_yoy",
        consensus="3.2%",
        fetched_at=after,
        release_time=release,
    )
    assert not late.eligible_for_surprise
    assert evaluate_surprise("headline_yoy", "3.5%", late) is None

    # Unknown/missing family must fail closed rather than borrowing semantics
    # from another event that happens to share the same metric_id.
    ambiguous = _observation(
        event_key="ambiguous",
        event_family="",
        metric_id="headline_mom",
        consensus="0.2%",
        fetched_at=before,
        release_time=release,
    )
    assert evaluate_surprise("headline_mom", "0.5%", ambiguous) is None

    assert parse_numeric("+162K") == (162.0, "K")
    assert parse_numeric("7.3M") == (7300.0, "K")
    assert parse_numeric("5.4%") == (5.4, "ppt")

    row = {
        "CalendarId": "123",
        "Forecast": "253K",
        "TEForecast": "263K",
        "Unit": "K",
        "URL": "/united-states/jobless-claims",
    }
    obs = te.observation_from_row(
        row,
        event_key="claims",
        event_family="claims",
        metric_id="initial_claims",
        release_time=release,
        fetched_at=before,
    )
    assert obs is not None
    assert obs.event_family == "claims"
    assert obs.consensus == "253K"
    assert obs.raw_value == "253K"
    assert obs.eligible_for_surprise

    previous = os.environ.pop(te.API_KEY_ENV, None)
    try:
        assert te.configured() is False
        assert te.fetch_calendar_rows(country="united states", indicator="cpi", start="2026-09-11", end="2026-09-11") == []
    finally:
        if previous is not None:
            os.environ[te.API_KEY_ENV] = previous

    print("consensus/surprise tests passed")


if __name__ == "__main__":
    main()
