from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as official
import v2_event_official_us_phase4 as phase4


def main() -> None:
    ism_rows = [
        ["January 2026", "5", "7"],
        ["February 2026", "2", "4"],
        ["September 2026", "1", "3"],
    ]
    parsed_ism = phase4._parse_ism_schedule_rows(ism_rows, 2026)
    assert (date(2026, 9, 1), "manufacturing") in parsed_ism
    assert (date(2026, 9, 3), "services") in parsed_ism

    advance = official._event(
        event_id="gdp-advance",
        dt=datetime(2026, 10, 29, 20, 30, tzinfo=official.TPE),
        title="美國國內生產毛額（GDP）－Advance Estimate",
        country="美國",
        tier="A",
        tags=("美國", "GDP"),
        source="BEA",
        source_url=official.BEA_SCHEDULE_URL,
        provider="official-us-bea-gdp",
    )
    second = official._event(
        event_id="gdp-second",
        dt=datetime(2026, 11, 25, 21, 30, tzinfo=official.TPE),
        title="美國國內生產毛額（GDP）－Second Estimate",
        country="美國",
        tier="A",
        tags=("美國", "GDP"),
        source="BEA",
        source_url=official.BEA_SCHEDULE_URL,
        provider="official-us-bea-gdp",
    )
    assert phase4._calibrate_gdp_event(advance).tier == "A"
    calibrated_second = phase4._calibrate_gdp_event(second)
    assert calibrated_second.tier == "B"
    assert calibrated_second.importance == 2
    assert "GDP修正估值" in calibrated_second.market_tags

    decision = official._event(
        event_id="fomc-2026-09-16",
        dt=official._dt_local(date(2026, 9, 16), 14, 0, official.NY),
        title="美國聯邦公開市場委員會（FOMC）利率決議",
        country="美國",
        tier="S",
        tags=("美國", "FOMC", "Fed"),
        source="Federal Reserve",
        source_url=official.FED_FOMC_URL,
        provider="official-us-fed-fomc",
        category="央行事件",
    )
    enriched = phase4._enrich_fomc_decision(decision)
    assert "SEP" in enriched.market_tags
    assert "含記者會" in enriched.market_tags
    minutes = phase4._fomc_minutes_event(decision)
    assert minutes.tier == "A"
    assert minutes.expects_result is False
    assert minutes.time_tpe.astimezone(official.NY).date() == date(2026, 10, 7)
    assert minutes.time_tpe.astimezone(official.NY).hour == 14

    chair_rows = [
        ["Economic Outlook", "Speech - Chairman Kevin Warsh", "10:00 a.m.", "18"],
        ["Acceptance Remarks", "Speech - Chairman Kevin Warsh", "2:00 p.m.", "19"],
        ["Economic Outlook", "Speech - Vice Chair Philip N. Jefferson", "9:00 a.m.", "20"],
    ]
    chair_events = phase4._parse_fed_chair_rows(chair_rows, 2026, 9)
    assert len(chair_events) == 1, chair_events
    assert chair_events[0].tier == "A"
    assert "Economic Outlook" in chair_events[0].title

    productivity = official._event(
        event_id="prod-2026-q3",
        dt=official._dt_local(date(2026, 11, 5), 8, 30, official.NY),
        title="美國勞動生產力與單位勞動成本（Productivity & Costs）",
        country="美國",
        tier="B",
        tags=("美國", "生產力"),
        source="BLS",
        source_url=phase4.BLS_PRODUCTIVITY_SCHEDULE_URL,
        provider="official-us-bls-productivity",
        importance=2,
    )
    object.__setattr__(productivity, "reference_quarter", (2026, 3))
    original = phase4.phase2._bls_quarter_observations
    try:
        phase4.phase2._bls_quarter_observations = lambda *_args, **_kwargs: {
            phase4.PRODUCTIVITY_SERIES["labor_productivity"]: [
                ((2026, 2), 1.4), ((2026, 3), 2.2)
            ],
            phase4.PRODUCTIVITY_SERIES["unit_labor_costs"]: [
                ((2026, 2), 1.0), ((2026, 3), 2.8)
            ],
        }
        metrics = phase4._productivity_metrics(
            productivity,
            datetime(2026, 11, 6, 0, 0, tzinfo=official.TPE),
            "test",
        )
    finally:
        phase4.phase2._bls_quarter_observations = original
    assert metrics[0]["actual"] == "2.2%"
    assert metrics[0]["previous"] == "1.4%"
    assert metrics[0]["is_primary"] is True
    assert metrics[1]["actual"] == "2.8%"

    print("Phase 4 US event tests passed")


if __name__ == "__main__":
    main()
