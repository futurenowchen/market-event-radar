from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official_us_phase3 as phase3


def main() -> None:
    g17_text = (
        "Release Date: September 18, 2026 "
        "Industrial production increased 0.4 percent in August after increasing 0.1 percent in July."
    )
    reference, values = phase3._parse_g17_release(g17_text)
    assert reference == date(2026, 8, 1), (reference, values)
    assert values["ip_mom"] == "0.4%", values
    assert values["previous_ip_mom"] == "0.1%", values

    durable_text = (
        "FOR IMMEDIATE RELEASE: Friday, September 25, 2026 "
        "New orders for manufactured durable goods in August increased $8.4 billion or 2.7 percent "
        "to $320.1 billion. This followed a 2.5 percent July decrease. "
        "Excluding transportation, new orders increased 0.5 percent. "
        "Excluding defense, new orders increased 1.9 percent."
    )
    reference, values = phase3._parse_durable_release(durable_text)
    assert reference == date(2026, 8, 1), (reference, values)
    assert values["headline_mom"] == "2.7%", values
    assert values["previous_mom"] == "-2.5%", values
    assert values["orders_level"] == "$320.1B", values
    assert values["ex_transport_mom"] == "0.5%", values
    assert values["ex_defense_mom"] == "1.9%", values

    housing_text = (
        "MONTHLY NEW RESIDENTIAL CONSTRUCTION, AUGUST 2026 "
        "Building Permits Privately-owned housing units authorized by building permits in August were at a "
        "seasonally adjusted annual rate of 1,420,000. This is 1.2 percent above the revised July rate of 1,403,000. "
        "Housing Starts Privately-owned housing starts in August were at a seasonally adjusted annual rate of "
        "1,385,000. This is 3.4 percent below the revised July estimate of 1,434,000."
    )
    reference, values = phase3._parse_housing_release(housing_text)
    assert reference == date(2026, 8, 1), (reference, values)
    assert values["starts_level"] == "1.385M", values
    assert values["starts_mom"] == "-3.4%", values
    assert values["previous_starts_level"] == "1.434M", values
    assert values["permits_level"] == "1.420M", values
    assert values["permits_mom"] == "1.2%", values
    assert values["previous_permits_level"] == "1.403M", values

    g17_schedule, _ = phase3._g17_schedule("test-phase3-g17")
    durable_schedule, _ = phase3._durable_schedule("test-phase3-durable")
    housing_schedule, _ = phase3._housing_schedule("test-phase3-housing")
    assert g17_schedule
    assert durable_schedule
    assert housing_schedule

    print("Phase 3 US parser tests passed")


if __name__ == "__main__":
    main()
