from __future__ import annotations

from datetime import datetime, timezone
import unittest

from market_event_radar.private_overlay import (
    PrivateOverlayObservation,
    VALUE_KIND_PROVIDER_FORECAST,
    VALUE_KIND_SURVEY_CONSENSUS,
    build_private_overlay,
    observations_from_mt5_canary,
)


RELEASE = datetime(2026, 9, 11, 12, 30, tzinfo=timezone.utc)
CAPTURE = datetime(2026, 9, 11, 4, 39, tzinfo=timezone.utc)


def _snapshot(actual: str = "3.4%") -> dict:
    return {
        "schema_version": 2,
        "generated_at_tpe": "2026-09-11T22:21:37+08:00",
        "events": [
            {
                "event_id": "official-us-bls-cpi-2026-09-11",
                "provider": "official-us-bls-cpi",
                "title": "CPI",
                "time_tpe": "2026-09-11T20:30:00+08:00",
                "status": "released",
                "metrics": [
                    {
                        "metric_id": "headline_yoy",
                        "actual": actual,
                        "previous": "3.4%",
                        "unit": "%",
                    }
                ],
            }
        ],
    }


def _observation(kind: str, value: str = "3.2%", captured_at: datetime = CAPTURE):
    return PrivateOverlayObservation(
        official_event_id="official-us-bls-cpi-2026-09-11",
        official_provider="official-us-bls-cpi",
        event_family="cpi",
        metric_id="headline_yoy",
        value=value,
        value_kind=kind,
        provider="fixture-provider",
        captured_at=captured_at,
        release_time=RELEASE,
        provider_event_id="fixture-event",
        unit="%",
    )


class PrivateOverlayTests(unittest.TestCase):
    def test_survey_consensus_produces_canonical_surprise(self):
        overlay = build_private_overlay(
            _snapshot(),
            [_observation(VALUE_KIND_SURVEY_CONSENSUS)],
            generated_at=datetime(2026, 9, 11, 13, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(overlay["canonical_surprise_count"], 1)
        self.assertEqual(overlay["diagnostic_comparison_count"], 0)
        row = overlay["observations"][0]
        self.assertTrue(row["eligible_for_canonical_surprise"])
        self.assertEqual(row["canonical_surprise"]["difference"], 0.2)
        self.assertEqual(row["canonical_surprise"]["direction"], "HOTTER_THAN_EXPECTED")
        self.assertIsNone(row["diagnostic_comparison"])

    def test_provider_forecast_is_diagnostic_only(self):
        overlay = build_private_overlay(
            _snapshot(),
            [_observation(VALUE_KIND_PROVIDER_FORECAST, "2.7%")],
            generated_at=datetime(2026, 9, 11, 13, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(overlay["canonical_surprise_count"], 0)
        self.assertEqual(overlay["diagnostic_comparison_count"], 1)
        row = overlay["observations"][0]
        self.assertFalse(row["eligible_for_canonical_surprise"])
        self.assertIsNone(row["canonical_surprise"])
        self.assertEqual(row["diagnostic_comparison"]["difference"], 0.7)
        self.assertEqual(row["diagnostic_comparison"]["direction"], "HOTTER_THAN_EXPECTED")

    def test_post_release_value_cannot_drive_any_comparison(self):
        late = _observation(
            VALUE_KIND_SURVEY_CONSENSUS,
            captured_at=datetime(2026, 9, 11, 12, 31, tzinfo=timezone.utc),
        )
        overlay = build_private_overlay(_snapshot(), [late])
        row = overlay["observations"][0]
        self.assertFalse(row["captured_before_release"])
        self.assertFalse(row["eligible_for_canonical_surprise"])
        self.assertIsNone(row["canonical_surprise"])
        self.assertIsNone(row["diagnostic_comparison"])

    def test_official_provider_mismatch_fails_closed(self):
        observation = PrivateOverlayObservation(
            official_event_id="official-us-bls-cpi-2026-09-11",
            official_provider="wrong-provider",
            event_family="cpi",
            metric_id="headline_yoy",
            value="3.2%",
            value_kind=VALUE_KIND_SURVEY_CONSENSUS,
            provider="fixture-provider",
            captured_at=CAPTURE,
            release_time=RELEASE,
        )
        overlay = build_private_overlay(_snapshot(), [observation])
        self.assertEqual(overlay["observation_count"], 0)
        self.assertEqual(overlay["skipped"][0]["reason"], "official_provider_mismatch")

    def test_mt5_canary_normalizer_never_promotes_forecast(self):
        report = {
            "provider": "metatrader5-economic-calendar",
            "results": [
                {
                    "status": "MATCHED",
                    "official_event_id": "official-us-bls-cpi-2026-09-11",
                    "official_provider": "official-us-bls-cpi",
                    "event_family": "cpi",
                    "metric_id": "headline_yoy",
                    "provider_forecast": "2.7",
                    "provider": "metatrader5-economic-calendar",
                    "provider_event_id": "123",
                    "provider_value_id": "456",
                    "captured_at": CAPTURE.isoformat(),
                    "release_time": RELEASE.isoformat(),
                    "unit": "%",
                }
            ],
        }
        observations = observations_from_mt5_canary(report)
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].value_kind, VALUE_KIND_PROVIDER_FORECAST)
        self.assertFalse(observations[0].eligible_for_canonical_surprise)


if __name__ == "__main__":
    unittest.main()
