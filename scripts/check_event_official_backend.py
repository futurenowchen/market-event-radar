from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as official
import v2_event_official_asia  # noqa: F401
import v2_event_official_taiwan as taiwan  # noqa: F401
import v2_event_official_resilience as resilience  # noqa: F401
import v2_event_official_taiwan_resilience  # noqa: F401
import v2_event_official_us_high_signal as us_high_signal  # noqa: F401
import v2_event_official_us_phase2 as us_phase2  # noqa: F401
import v2_event_official_us_claims  # noqa: F401
import v2_event_official_us_phase3 as us_phase3  # noqa: F401
import v2_event_official_us_phase4 as us_phase4  # noqa: F401
import v2_event_company_ir as company_ir  # noqa: F401


def main() -> None:
    now = datetime.now(official.TPE)
    start = now - timedelta(hours=48)
    end = now + timedelta(days=35)
    macro, health = official.collect_official_macro(start, end, "ci-smoke")

    print("source_health:")
    for name, ok in sorted(health.items()):
        print(f"  {name}: {'ok' if ok else 'failed'}")

    print("live_schedule_reachability:")
    probes = {
        "bls_cpi": resilience.BLS_CPI_SCHEDULE_URL,
        "bls_ppi": us_high_signal.PPI_SCHEDULE_URL,
        "bls_jolts": us_phase2.JOLTS_SCHEDULE_URL,
        "bls_eci": us_phase2.ECI_SCHEDULE_URL,
        "bls_productivity": us_phase4.BLS_PRODUCTIVITY_SCHEDULE_URL,
        "census_retail": us_phase2.CENSUS_CALENDAR_URL,
        "dol_claims": us_phase2.CLAIMS_RELEASES_URL,
        "fed_g17": us_phase3.FED_G17_URL,
        "fed_calendar": official.FED_FOMC_URL,
        "ism_calendar": us_phase4.ISM_CALENDAR_URL,
        "census_durable": us_phase3.DURABLE_SCHEDULE_URL,
        "census_housing": us_phase3.HOUSING_SCHEDULE_URL,
        "tw_cpi": taiwan.TW_CPI_SCHEDULE_URL,
        "kr_cpi": resilience.KR_CPI_SCHEDULE_URL,
    }
    for name, url in probes.items():
        print(f"  {name}: {'ok' if official._fetch_text(url, 'ci-live') else 'fallback'}")

    print("events:")
    for event in macro:
        metrics = getattr(event, "metrics", ())
        metric_note = f" | metrics={len(metrics)}" if metrics else ""
        print(
            f"  {event.time_tpe.isoformat()} | {event.tier} | {event.country} | "
            f"{event.title} | provider={event.provider} | actual={event.actual or '-'}{metric_note}"
        )

    groups = {
        "United States": (
            "us_bls", "us_bea", "us_fed", "us_census", "us_dol",
            "us_fed_g17", "us_census_m3", "us_census_housing", "us_ism", "us_fed_chair",
        ),
        "Taiwan": ("tw_dgbas", "tw_cbc"),
        "Japan": ("jp_stat", "jp_esri", "jp_boj"),
        "South Korea": ("kr_mods", "kr_bok"),
    }
    failures = [label for label, keys in groups.items() if not any(health.get(key) for key in keys)]
    if failures:
        raise SystemExit("No usable official source for: " + ", ".join(failures))

    providers = {event.provider for event in macro}
    required_providers = {
        "official-us-bls-cpi",
        "official-us-bls-ppi",
        "official-us-bls-nfp",
        "official-tw-dgbas-cpi",
        "official-kr-mods-cpi",
        "official-kr-mods-industry",
    }
    missing = sorted(required_providers - providers)
    if missing:
        raise SystemExit("Resilient official schedules missing providers: " + ", ".join(missing))

    jolts_schedule, _ = us_phase2._jolts_schedule("ci-jolts-schedule")
    eci_schedule, _ = us_phase2._eci_schedule("ci-eci-schedule")
    retail_schedule, _ = us_phase2._retail_schedule("ci-retail-schedule")
    g17_schedule, _ = us_phase3._g17_schedule("ci-g17-schedule")
    durable_schedule, _ = us_phase3._durable_schedule("ci-durable-schedule")
    housing_schedule, _ = us_phase3._housing_schedule("ci-housing-schedule")
    ism_schedule, _ = us_phase4._ism_schedule("ci-ism-schedule")
    productivity_schedule, _ = us_phase4._productivity_schedule("ci-productivity-schedule")
    schedules = {
        "JOLTS": jolts_schedule,
        "ECI": eci_schedule,
        "Retail Sales": retail_schedule,
        "G17": g17_schedule,
        "Durable Goods": durable_schedule,
        "Housing": housing_schedule,
        "ISM": ism_schedule,
        "Productivity": productivity_schedule,
    }
    unavailable = [name for name, rows in schedules.items() if not rows]
    if unavailable:
        raise SystemExit("Official/fallback schedules unavailable: " + ", ".join(unavailable))
    print("US extended schedules: ok " + ", ".join(f"{name}={len(rows)}" for name, rows in schedules.items()))

    bls_probe = official._bls_observations(
        ["CUUR0000SA0", "WPUFD4", us_phase2.JOLTS_SERIES["openings"]],
        now,
        "ci-bls-api",
    )
    for series_id, label in (
        ("CUUR0000SA0", "CPI"),
        ("WPUFD4", "PPI"),
        (us_phase2.JOLTS_SERIES["openings"], "JOLTS"),
    ):
        if not bls_probe.get(series_id):
            raise SystemExit(f"BLS keyless Public Data API returned no {label} observations")

    eci_probe = us_phase2._bls_quarter_observations(
        [us_phase2.ECI_SERIES["comp_qoq"]], now, "ci-eci-api"
    ).get(us_phase2.ECI_SERIES["comp_qoq"], [])
    if not eci_probe:
        raise SystemExit("BLS keyless Public Data API returned no ECI observations")

    productivity_probe = us_phase2._bls_quarter_observations(
        list(us_phase4.PRODUCTIVITY_SERIES.values()), now, "ci-productivity-api"
    )
    for series_id, label in (
        (us_phase4.PRODUCTIVITY_SERIES["labor_productivity"], "labor productivity"),
        (us_phase4.PRODUCTIVITY_SERIES["unit_labor_costs"], "unit labor costs"),
    ):
        if not productivity_probe.get(series_id):
            raise SystemExit(f"BLS keyless Public Data API returned no {label} observations")

    extended_providers = {
        "official-us-fed-g17",
        "official-us-census-durable",
        "official-us-census-housing",
        "official-us-ism-manufacturing",
        "official-us-fed-fomc-minutes",
    }
    if not extended_providers.issubset(providers):
        missing_extended = sorted(extended_providers - providers)
        raise SystemExit("Extended US schedules missing providers: " + ", ".join(missing_extended))

    ism_events = [event for event in macro if event.provider.startswith("official-us-ism-")]
    if not ism_events or any(event.expects_result for event in ism_events):
        raise SystemExit("ISM schedule-only policy missing or expects_result is enabled")
    if any(event.actual or event.previous or event.forecast for event in ism_events):
        raise SystemExit("ISM licensed values leaked into official-free feed")

    rich = [
        event for event in macro
        if event.provider.startswith("official-us-") and getattr(event, "metrics", ())
    ]
    if not rich:
        raise SystemExit("No high-signal US release carried a metrics bundle")

    if any("tradingeconomics" in event.provider.lower() for event in macro):
        raise SystemExit("Trading Economics leaked into official macro path")

    if not official._official_macro_ready(macro, health):
        raise SystemExit("official_macro_ready unexpectedly false")

    ir_start = datetime(2026, 8, 26, 0, 0, tzinfo=official.TPE)
    ir_end = datetime(2026, 8, 28, 0, 0, tzinfo=official.TPE)
    ir_events = company_ir.official_ir_events(ir_start, ir_end)
    if not any(
        event.symbol == "NVDA"
        and event.provider == "official-company-ir"
        and event.time_tpe == datetime(2026, 8, 27, 4, 20, tzinfo=official.TPE)
        for event in ir_events
    ):
        raise SystemExit("NVIDIA official IR anchor missing or shifted")

    print(f"official backend smoke check passed: {len(macro)} macro event(s) in the 35-day CI horizon")


if __name__ == "__main__":
    main()
