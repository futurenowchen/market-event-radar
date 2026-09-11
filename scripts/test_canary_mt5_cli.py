from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.canary_mt5_consensus import build_report
from scripts.test_mt5_consensus_canary import fixture


def main() -> None:
    snapshot = {
        "schema_version": 2,
        "events": [
            {
                "event_id": "official-us-bls-cpi-2026-09-11",
                "provider": "official-us-bls-cpi",
                "time_tpe": "2026-09-11T20:30:00+08:00",
                "metrics": [
                    {"metric_id": "headline_yoy", "label": "Headline YoY", "previous": "3.4%", "unit": "%"},
                    {"metric_id": "core_mom", "label": "Core MoM", "previous": "0.2%", "unit": "%"},
                ],
            }
        ],
    }
    report = build_report(fixture(), snapshot)
    assert report["candidate_observation_count"] == 2
    assert report["matched_official_count"] == 2
    assert report["pre_release_match_count"] == 2
    assert report["promotion_status"] == "NOT_PROMOTED"
    assert report["results"][0]["official_event_id"] == "official-us-bls-cpi-2026-09-11"
    assert report["results"][0]["provider_forecast"] == "3.4"
    print("MT5 canary CLI tests passed")


if __name__ == "__main__":
    main()
