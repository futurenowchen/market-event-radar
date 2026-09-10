from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as backend
import v2_event_official_us_phase2 as phase2


def _series(*rows: tuple[int, int, float]):
    return [(date(year, month, 1), value) for year, month, value in rows]


def main() -> None:
    assert phase2._parse_release_day("Sep. 29, 2026") == date(2026, 9, 29)
    assert phase2._parse_reference_month("August 2026") == date(2026, 8, 1)
    assert phase2._parse_reference_quarter("Third Quarter 2026") == (2026, 3)

    retail_text = (
        "Advance estimates of U.S. retail and food services sales for July 2026, "
        "adjusted for seasonal variation and holiday and trading-day differences, "
        "but not for price changes, were $763.6 billion, down 0.6 percent from the "
        "previous month, but up 5.0 percent from July 2025. The May 2026 to June 2026 "
        "percent change was unrevised from up 0.2 percent."
    )
    retail_month, retail_values = phase2._parse_retail_release_text(retail_text)
    assert retail_month == date(2026, 7, 1)
    assert retail_values["headline_mom"] == "-0.6%"
    assert retail_values["headline_yoy"] == "5%"
    assert retail_values["previous_mom"] == "0.2%"

    claims_text = (
        "September 10, 2026 Unemployment Insurance Weekly Claims Report "
        "In the week ending September 5, the advance figure for seasonally adjusted "
        "initial claims was 221,000, a decrease of 5,000 from the previous week's revised level. "
        "The previous week's level was revised up by 1,000 from 225,000 to 226,000. "
        "The 4-week moving average was 224,500, a decrease of 2,000 from the previous week's revised average."
    )
    claims_day, claims_values = phase2._parse_claims_release_text(claims_text)
    assert claims_day == date(2026, 9, 10)
    assert claims_values["initial_claims"] == "221K"
    assert claims_values["previous_claims"] == "226K"
    assert claims_values["four_week_average"] == "224.5K"

    original_bls = backend._bls_observations
    original_quarter = phase2._bls_quarter_observations
    try:
        jolts_sample = {
            phase2.JOLTS_SERIES["openings"]: _series((2026, 7, 7200), (2026, 8, 7350)),
            phase2.JOLTS_SERIES["hires"]: _series((2026, 7, 5300), (2026, 8, 5400)),
            phase2.JOLTS_SERIES["quits"]: _series((2026, 7, 3200), (2026, 8, 3300)),
            phase2.JOLTS_SERIES["layoffs"]: _series((2026, 7, 1800), (2026, 8, 1750)),
        }

        def fake_bls(series_ids, now, refresh_token):
            del now, refresh_token
            return {series_id: jolts_sample.get(series_id, []) for series_id in series_ids}

        backend._bls_observations = fake_bls
        jolts_event = backend._event(
            event_id="test-jolts",
            dt=datetime.fromisoformat("2026-09-29T22:00:00+08:00"),
            title="JOLTS",
            country="美國",
            tier="A",
            tags=("JOLTS",),
            source="BLS",
            source_url=phase2.JOLTS_SCHEDULE_URL,
            provider="official-us-bls-jolts",
        )
        phase2._set_reference(jolts_event, "reference_month", date(2026, 8, 1))
        jolts_metrics = phase2._jolts_metrics(
            jolts_event,
            datetime.fromisoformat("2026-09-29T22:30:00+08:00"),
            "test",
        )
        assert len(jolts_metrics) == 4
        assert next(row for row in jolts_metrics if row["is_primary"])["actual"] == "7.3M"
        assert next(row for row in jolts_metrics if row["is_primary"])["previous"] == "7.2M"

        eci_sample = {
            phase2.ECI_SERIES["comp_qoq"]: [((2026, 2), 0.9), ((2026, 3), 1.0)],
            phase2.ECI_SERIES["wages_qoq"]: [((2026, 2), 0.8), ((2026, 3), 0.9)],
            phase2.ECI_SERIES["comp_yoy"]: [((2026, 2), 3.6), ((2026, 3), 3.7)],
            phase2.ECI_SERIES["wages_yoy"]: [((2026, 2), 3.7), ((2026, 3), 3.8)],
        }

        def fake_quarter(series_ids, now, refresh_token):
            del now, refresh_token
            return {series_id: eci_sample.get(series_id, []) for series_id in series_ids}

        phase2._bls_quarter_observations = fake_quarter
        eci_event = backend._event(
            event_id="test-eci",
            dt=datetime.fromisoformat("2026-10-30T20:30:00+08:00"),
            title="ECI",
            country="美國",
            tier="A",
            tags=("ECI",),
            source="BLS",
            source_url=phase2.ECI_SCHEDULE_URL,
            provider="official-us-bls-eci",
        )
        phase2._set_reference(eci_event, "reference_quarter", (2026, 3))
        eci_metrics = phase2._eci_metrics(
            eci_event,
            datetime.fromisoformat("2026-10-30T21:00:00+08:00"),
            "test",
        )
        assert len(eci_metrics) == 4
        assert next(row for row in eci_metrics if row["is_primary"])["actual"] == "1%"
        assert next(row for row in eci_metrics if row["is_primary"])["previous"] == "0.9%"
    finally:
        backend._bls_observations = original_bls
        phase2._bls_quarter_observations = original_quarter

    print("US Phase 2 tests passed")


if __name__ == "__main__":
    main()
