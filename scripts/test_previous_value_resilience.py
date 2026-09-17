from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as backend
import v2_event_official_previous_resilience as previous
import v2_event_official_us_phase2 as phase2


def main() -> None:
    calendar = """
    2026 FOMC Meetings
    June 16-17*
    Minutes Released July 8, 2026
    July 28-29
    Minutes Released August 19, 2026
    September 15-16*
    Minutes Released October 7, 2026
    December 8-9*
    """
    assert previous._previous_fomc_meeting_day(calendar, date(2026, 9, 16)) == date(2026, 7, 29)

    original_fomc = previous._BASE_FOMC_EVENTS
    original_fetch = backend._fetch_text
    try:
        event = backend._event(
            event_id="official-us-fed-fomc-2026-09-16",
            dt=datetime.fromisoformat("2026-09-17T02:00:00+08:00"),
            title="美國聯邦公開市場委員會（FOMC）利率決議",
            country="美國",
            tier="S",
            tags=("美國", "FOMC"),
            source="Federal Reserve",
            source_url=backend.FED_FOMC_URL,
            provider="official-us-fed-fomc",
            actual="3.75–4%",
        )

        def fake_fomc(start, end, token):
            del start, end, token
            return [event], True

        def fake_fetch(url, token):
            del token
            if url == backend.FED_FOMC_URL:
                return calendar
            if "20260729a.htm" in url:
                return (
                    "The Committee decided to maintain the target range for the federal funds rate "
                    "at 3-1/2 to 3-3/4 percent."
                )
            return ""

        previous._BASE_FOMC_EVENTS = fake_fomc
        backend._fetch_text = fake_fetch
        rows, ok = previous._us_fomc_events_with_previous(
            datetime.fromisoformat("2026-09-16T00:00:00+08:00"),
            datetime.fromisoformat("2026-09-18T00:00:00+08:00"),
            "test",
        )
        assert ok and len(rows) == 1
        assert rows[0].actual == "3.75–4%"
        assert rows[0].previous == "3.5–3.75%"
    finally:
        previous._BASE_FOMC_EVENTS = original_fomc
        backend._fetch_text = original_fetch

    base = [
        phase2._metric(
            "headline_mom",
            "零售與餐飲銷售 MoM",
            actual="1.2%",
            previous="",
            unit="%",
            is_primary=True,
            source_series="Census Economic Indicators / MARTS",
        )
    ]
    merged = previous._merge_retail_previous(
        base,
        {
            "headline_mom": "1.2%",
            "previous_mom": "-0.6%",
            "headline_yoy": "5.0%",
            "sales_level": "$773.9B",
        },
    )
    primary = next(row for row in merged if row.get("is_primary"))
    assert primary["actual"] == "1.2%"
    assert primary["previous"] == "-0.6%"
    assert primary["source_series"] == "Census MARTS release PDF"

    pdf_text = (
        "Advance estimates of U.S. retail and food services sales for August 2026 "
        "were $773.9 billion, up 1.2 percent from the previous month, but up 5.0 percent "
        "from August 2025. The June 2026 to July 2026 percent change was revised from "
        "down 0.6 percent to down 0.5 percent."
    )
    original_pdf_fetch = previous._fetch_retail_pdf_text
    try:
        previous._fetch_retail_pdf_text = lambda reference: pdf_text
        values = previous._retail_pdf_values(date(2026, 8, 1))
        assert values["headline_mom"] == "1.2%"
        assert values["previous_mom"] == "-0.5%"
        assert values["sales_level"] == "$773.9B"
    finally:
        previous._fetch_retail_pdf_text = original_pdf_fetch

    series_text = """
RETAIL & FOOD SERVICES
YEAR      JAN       FEB       MAR       APR       MAY       JUN       JUL       AUG
2026   734503    741278    754013    759097    766876    768553    764710    773900

SEASONAL FACTORS
2026     0.914     0.882     1.011     0.998     1.043     1.008     1.033     1.015
"""
    parsed = previous._parse_adjusted_total_series(series_text)
    assert parsed[date(2026, 6, 1)] == 768553
    assert parsed[date(2026, 7, 1)] == 764710

    original_fetch = backend._fetch_text
    try:
        backend._fetch_text = lambda url, token: series_text if url == previous.RETAIL_ADJUSTED_TOTAL_URL else ""
        derived = previous._retail_timeseries_previous(date(2026, 8, 1), "test")
        assert derived == "-0.5%"
    finally:
        backend._fetch_text = original_fetch

    print("Previous-value resilience tests passed")


if __name__ == "__main__":
    main()
