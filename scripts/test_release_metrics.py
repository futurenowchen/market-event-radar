from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as backend
import v2_event_release_metrics as metrics


def _series(*rows: tuple[int, int, float]):
    return [(date(year, month, 1), value) for year, month, value in rows]


def main() -> None:
    original = backend._bls_observations
    try:
        sample = {
            "CUUR0000SA0": _series(
                (2025, 7, 300.0), (2025, 8, 301.0),
                (2026, 6, 308.0), (2026, 7, 309.0), (2026, 8, 312.0),
            ),
            "CUSR0000SA0": _series((2026, 6, 308.0), (2026, 7, 309.0), (2026, 8, 312.0)),
            "CUUR0000SA0L1E": _series(
                (2025, 7, 310.0), (2025, 8, 311.0),
                (2026, 7, 317.0), (2026, 8, 319.0),
            ),
            "CUSR0000SA0L1E": _series((2026, 6, 315.0), (2026, 7, 317.0), (2026, 8, 319.0)),
            "WPUFD4": _series(
                (2025, 7, 140.0), (2025, 8, 141.0),
                (2026, 7, 147.0), (2026, 8, 149.0),
            ),
            "WPSFD4": _series((2026, 6, 146.0), (2026, 7, 147.0), (2026, 8, 149.0)),
            "WPUFD49116": _series(
                (2025, 7, 130.0), (2025, 8, 131.0),
                (2026, 7, 136.0), (2026, 8, 138.0),
            ),
            "WPSFD49116": _series((2026, 6, 135.0), (2026, 7, 136.0), (2026, 8, 138.0)),
            "CES0000000001": _series((2026, 6, 159000.0), (2026, 7, 159150.0), (2026, 8, 159312.0)),
            "LNS14000000": _series((2026, 7, 4.0), (2026, 8, 4.1)),
            "CES0500000003": _series(
                (2025, 7, 36.00), (2025, 8, 36.10),
                (2026, 6, 37.00), (2026, 7, 37.10), (2026, 8, 37.21),
            ),
        }

        def fake_bls(series_ids, now, refresh_token):
            del now, refresh_token
            return {series_id: sample.get(series_id, []) for series_id in series_ids}

        backend._bls_observations = fake_bls

        cpi_release = datetime.fromisoformat("2026-09-11T20:30:00+08:00")
        before = datetime.fromisoformat("2026-09-10T22:00:00+08:00")
        after = datetime.fromisoformat("2026-09-11T21:00:00+08:00")
        cpi_before = metrics._bls_bundle("cpi", cpi_release, before, "test")
        cpi_primary_before = next(row for row in cpi_before if row["is_primary"])
        assert cpi_primary_before["actual"] == ""
        assert cpi_primary_before["previous"]
        cpi_after = metrics._bls_bundle("cpi", cpi_release, after, "test")
        assert len(cpi_after) == 4
        assert next(row for row in cpi_after if row["is_primary"])["actual"]

        ppi_release = datetime.fromisoformat("2026-09-10T20:30:00+08:00")
        ppi_after = metrics._bls_bundle("ppi", ppi_release, after, "test")
        assert {row["metric_id"] for row in ppi_after} == {
            "headline_yoy", "headline_mom", "core_yoy", "core_mom"
        }
        assert next(row for row in ppi_after if row["is_primary"])["actual"]

        nfp_release = datetime.fromisoformat("2026-09-04T20:30:00+08:00")
        nfp_after = metrics._bls_bundle("nfp", nfp_release, datetime.fromisoformat("2026-09-04T21:00:00+08:00"), "test")
        assert {row["metric_id"] for row in nfp_after} == {
            "payroll_change", "unemployment_rate", "avg_hourly_earnings_mom", "avg_hourly_earnings_yoy"
        }
        assert next(row for row in nfp_after if row["metric_id"] == "payroll_change")["actual"] == "+162K"

        print("release metric tests passed")
    finally:
        backend._bls_observations = original


if __name__ == "__main__":
    main()
