from __future__ import annotations

from datetime import date
import unittest

import v2_event_official_asia as asia


SCHEDULE = """
Table : 2026
Date of MPM | Release Schedule
Jan. 22 (Thurs.), 23 (Fri.) | Jan. 23 (Fri.) | Feb. 2 (Mon.) | Mar. 25 (Wed.)
Mar. 18 (Wed.), 19 (Thurs.) | - | Mar. 30 (Mon.) | May 7 (Thurs.)
Apr. 27 (Mon.), 28 (Tues.) | Apr. 28 (Tues.) | May 12 (Tues.) | June 19 (Fri.)
June 15 (Mon.), 16 (Tues.) | - | June 24 (Wed.) | Aug. 5 (Wed.)
July 30 (Thurs.), 31 (Fri.) | July 31 (Fri.) | Aug. 10 (Mon.) | Sept. 28 (Mon.)
Sept. 17 (Thurs.), 18 (Fri.) | - | Oct. 1 (Thurs.) | Nov. 5 (Thurs.)
Oct. 29 (Thurs.), 30 (Fri.) | Oct. 30 (Fri.) | Nov. 10 (Tues.) | Dec. 23 (Wed.)
Dec. 17 (Thurs.), 18 (Fri.) | - | Dec. 28 (Mon.) | Jan. 27 (Wed.), 2027
Table : 2027
"""


class BojScheduleTests(unittest.TestCase):
    def test_only_two_day_mpm_ranges_become_meeting_days(self):
        days = asia.parse_boj_meeting_days(SCHEDULE, 2026)
        self.assertIn(date(2026, 9, 18), days)
        self.assertIn(date(2026, 7, 31), days)
        self.assertNotIn(date(2026, 9, 28), days)
        self.assertNotIn(date(2026, 10, 1), days)
        self.assertEqual(len(days), 8)

    def test_policy_rate_parser_reads_guideline_not_basic_loan_rate(self):
        text = """
        Change in the Guideline for Money Market Operations.
        The Bank will encourage the uncollateralized overnight call rate
        to remain at around 1.25 percent.
        The basic loan rate will be 1.50 percent.
        """
        self.assertEqual(asia.parse_boj_policy_rate(text), "1.25%")

    def test_previous_rate_shape(self):
        text = """
        Statement on Monetary Policy.
        The Bank will encourage the uncollateralized overnight call rate
        to remain at around 1.0 percent.
        """
        self.assertEqual(asia.parse_boj_policy_rate(text), "1%")


if __name__ == "__main__":
    unittest.main()
