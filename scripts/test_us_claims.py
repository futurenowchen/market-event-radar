from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official_us_claims as claims


def main() -> None:
    text = """
    TRANSMISSION OF MATERIALS IN THIS RELEASE IS EMBARGOED UNTIL
    8:30 A.M. (Eastern) Thursday, September 10, 2026
    UNEMPLOYMENT INSURANCE WEEKLY CLAIMS
    SEASONALLY ADJUSTED DATA
    In the week ending September 5, the advance figure for seasonally adjusted
    initial claims was 206,000, a decrease of 1,000 from the previous week's revised level.
    The previous week's level was revised up by 1,000 from 206,000 to 207,000.
    The 4-week moving average was 206,000, a decrease of 1,500 from the previous week's revised average.
    """
    release_day, values = claims._parse_claims_pdf_text(text)
    assert release_day == date(2026, 9, 10)
    assert values["initial_claims"] == "206K"
    assert values["previous_claims"] == "207K"
    assert values["four_week_average"] == "206K"

    unrevised = """
    8:30 A.M. (Eastern) Thursday, September 17, 2026
    UNEMPLOYMENT INSURANCE WEEKLY CLAIMS
    The advance figure for seasonally adjusted initial claims was 210,500.
    The previous week's level was unrevised at 206,000.
    The 4-week moving average was 207,250.
    """
    release_day, values = claims._parse_claims_pdf_text(unrevised)
    assert release_day == date(2026, 9, 17)
    assert values["initial_claims"] == "210.5K"
    assert values["previous_claims"] == "206K"
    assert values["four_week_average"] == "207.2K"

    print("US claims PDF parser tests passed")


if __name__ == "__main__":
    main()
