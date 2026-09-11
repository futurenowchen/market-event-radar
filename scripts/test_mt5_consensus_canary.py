from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_event_radar.providers.mt5_calendar import (
    PROVIDER,
    iter_candidate_observations,
    observation_from_row,
    release_time_utc,
    target_key_for_row,
)


def fixture() -> dict:
    return {
        "schema_version": 1,
        "provider": PROVIDER,
        "capture_time_server": "2026-09-11T06:00:00",
        "capture_time_gmt": "2026-09-11T03:00:00",
        "server_utc_offset_seconds": 10800,
        "terminal_language": "English",
        "country_code": "US",
        "currency": "USD",
        "rows": [
            {
                "provider_event_id": "840030001",
                "provider_value_id": "90001",
                "event_code": "us-cpi-yy",
                "event_name": "CPI y/y",
                "sector": "CALENDAR_SECTOR_PRICES",
                "importance": "CALENDAR_IMPORTANCE_HIGH",
                "unit": "CALENDAR_UNIT_PERCENT",
                "multiplier": "CALENDAR_MULTIPLIER_NONE",
                "digits": 1,
                "source_url": "https://www.bls.gov/cpi/",
                "release_time_server": "2026-09-11T15:30:00",
                "period_server": "2026-08-01T00:00:00",
                "forecast": 3.4,
                "previous": 3.4,
                "revised_previous": None,
                "actual": None,
            },
            {
                "provider_event_id": "840030002",
                "provider_value_id": "90002",
                "event_code": "us-core-cpi-mm",
                "event_name": "Core CPI m/m",
                "sector": "CALENDAR_SECTOR_PRICES",
                "importance": "CALENDAR_IMPORTANCE_HIGH",
                "unit": "CALENDAR_UNIT_PERCENT",
                "multiplier": "CALENDAR_MULTIPLIER_NONE",
                "digits": 1,
                "source_url": "https://www.bls.gov/cpi/",
                "release_time_server": "2026-09-11T15:30:00",
                "period_server": "2026-08-01T00:00:00",
                "forecast": 0.2,
                "previous": 0.2,
                "revised_previous": None,
                "actual": None,
            },
            {
                "provider_event_id": "840040001",
                "provider_value_id": "90003",
                "event_code": "us-core-ppi-yy",
                "event_name": "Core PPI y/y",
                "sector": "CALENDAR_SECTOR_PRICES",
                "importance": "CALENDAR_IMPORTANCE_LOW",
                "unit": "CALENDAR_UNIT_PERCENT",
                "multiplier": "CALENDAR_MULTIPLIER_NONE",
                "digits": 1,
                "source_url": "https://www.bls.gov/ppi/",
                "release_time_server": "2026-09-10T15:30:00",
                "period_server": "2026-08-01T00:00:00",
                "forecast": 4.5,
                "previous": 4.2,
                "revised_previous": None,
                "actual": 4.6,
            },
        ],
    }


def main() -> None:
    payload = fixture()
    first = payload["rows"][0]
    assert target_key_for_row(first) == ("cpi", "headline_yoy")
    assert release_time_utc(payload, first) == datetime(2026, 9, 11, 12, 30, tzinfo=timezone.utc)

    observation = observation_from_row(payload, first)
    assert observation is not None
    assert observation.provider_forecast == "3.4"
    assert observation.previous == "3.4"
    assert observation.actual == ""
    assert observation.captured_at == datetime(2026, 9, 11, 3, 0, tzinfo=timezone.utc)
    assert observation.captured_before_release

    observations = list(iter_candidate_observations(payload))
    assert [(item.event_family, item.metric_id) for item in observations] == [
        ("cpi", "headline_yoy"),
        ("cpi", "core_mom"),
    ]

    # Core PPI must fail closed: the provider's common core definition does not
    # match our official BLS core series that also excludes trade services.
    assert target_key_for_row(payload["rows"][2]) is None

    late = dict(payload)
    late["capture_time_gmt"] = "2026-09-11T13:00:00"
    late_observation = observation_from_row(late, first)
    assert late_observation is not None
    assert not late_observation.captured_before_release

    # Canonical event_code mapping tests
    assert target_key_for_row({"event_code": "consumer-price-index-yy"}) == ("cpi", "headline_yoy")
    assert target_key_for_row({"event_code": "consumer-price-index-mm"}) == ("cpi", "headline_mom")
    assert target_key_for_row({"event_code": "consumer-price-index-ex-food-energy-yy"}) == ("cpi", "core_yoy")
    assert target_key_for_row({"event_code": "consumer-price-index-ex-food-energy-mm"}) == ("cpi", "core_mom")
    assert target_key_for_row({"event_code": "producer-price-index-yy"}) == ("ppi", "headline_yoy")
    assert target_key_for_row({"event_code": "producer-price-index-mm"}) == ("ppi", "headline_mom")
    assert target_key_for_row({"event_code": "initial-jobless-claims"}) == ("claims", "initial_claims")

    # Localized Chinese names fallback
    assert target_key_for_row({"event_name": "CPI 年率y/y"}) == ("cpi", "headline_yoy")
    assert target_key_for_row({"event_name": "核心CPI月率 m/m"}) == ("cpi", "core_mom")
    assert target_key_for_row({"event_name": "初领失业金人数"}) == ("claims", "initial_claims")
    assert target_key_for_row({"event_name": "生产者物价指数（PPI）年率y/y"}) == ("ppi", "headline_yoy")

    # Core PPI must fail closed under both code and name lookups
    assert target_key_for_row({"event_code": "producer-price-index-ex-food-energy-yy"}) is None
    assert target_key_for_row({"event_code": "producer-price-index-ex-food-energy-mm"}) is None
    assert target_key_for_row({"event_name": "核心生产者物价指数(PPI)年率 y/y"}) is None

    # Unmapped events return None
    assert target_key_for_row({"event_code": "michigan-inflation-expectations"}) is None
    assert target_key_for_row({"event_code": "continuing-jobless-claims"}) is None

    print("MT5 consensus canary helper tests passed")


if __name__ == "__main__":
    main()
