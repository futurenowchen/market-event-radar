from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as official
import v2_event_official_asia  # noqa: F401  # install source-format-specific JP parsers
import v2_event_official_taiwan as taiwan  # noqa: F401  # install hardened TW schedules
import v2_event_official_resilience as resilience  # noqa: F401  # install resilient BLS/KR schedules
import v2_event_official_taiwan_resilience  # noqa: F401  # install resilient TW results
import v2_event_official_us_high_signal as us_high_signal  # noqa: F401  # install PPI + rich US metrics
import v2_event_official_us_phase2 as us_phase2  # noqa: F401  # install retail/JOLTS/ECI/claims
import v2_event_company_ir as company_ir  # noqa: F401  # install official company IR fallbacks


def main() -> None:
    now = datetime.now(official.TPE)
    start = now - timedelta(hours=48)
    # 35 days covers the monthly CPI/PPI/NFP cadence without turning a quiet
    # calendar position into a false CI failure. Phase 2 schedule contracts are
    # checked separately below instead of requiring every family in this window.
    end = now + timedelta(days=35)
    macro, health = official.collect_official_macro(start, end, "ci-smoke")

    print("source_health:")
    for name, ok in sorted(health.items()):
        print(f"  {name}: {'ok' if ok else 'failed'}")

    print("live_schedule_reachability:")
    print(f"  bls_cpi: {'ok' if official._fetch_text(resilience.BLS_CPI_SCHEDULE_URL, 'ci-live') else 'fallback'}")
    print(f"  bls_ppi: {'ok' if official._fetch_text(us_high_signal.PPI_SCHEDULE_URL, 'ci-live') else 'fallback'}")
    print(f"  bls_jolts: {'ok' if official._fetch_text(us_phase2.JOLTS_SCHEDULE_URL, 'ci-live') else 'fallback'}")
    print(f"  bls_eci: {'ok' if official._fetch_text(us_phase2.ECI_SCHEDULE_URL, 'ci-live') else 'fallback'}")
    print(f"  census_retail: {'ok' if official._fetch_text(us_phase2.CENSUS_CALENDAR_URL, 'ci-live') else 'fallback'}")
    print(f"  dol_claims: {'ok' if official._fetch_text(us_phase2.CLAIMS_RELEASES_URL, 'ci-live') else 'fallback'}")
    print(f"  tw_cpi: {'ok' if official._fetch_text(taiwan.TW_CPI_SCHEDULE_URL, 'ci-live') else 'fallback'}")
    print(f"  kr_cpi: {'ok' if official._fetch_text(resilience.KR_CPI_SCHEDULE_URL, 'ci-live') else 'fallback'}")

    print("events:")
    for event in macro:
        metrics = getattr(event, "metrics", ())
        metric_note = f" | metrics={len(metrics)}" if metrics else ""
        print(
            f"  {event.time_tpe.isoformat()} | {event.tier} | {event.country} | "
            f"{event.title} | provider={event.provider} | actual={event.actual or '-'}{metric_note}"
        )

    groups = {
        "United States": ("us_bls", "us_bea", "us_fed", "us_census", "us_dol"),
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
    if not jolts_schedule:
        raise SystemExit("JOLTS schedule unavailable")
    if not eci_schedule:
        raise SystemExit("ECI schedule unavailable")
    if not retail_schedule:
        raise SystemExit("Retail Sales schedule unavailable")
    print(
        "Phase 2 schedules: ok "
        f"(JOLTS={len(jolts_schedule)}, ECI={len(eci_schedule)}, retail={len(retail_schedule)})"
    )

    bls_probe = official._bls_observations(
        [
            "CUUR0000SA0",
            "WPUFD4",
            us_phase2.JOLTS_SERIES["openings"],
        ],
        now,
        "ci-bls-api",
    )
    if not bls_probe.get("CUUR0000SA0"):
        raise SystemExit("BLS keyless Public Data API returned no CPI observations")
    if not bls_probe.get("WPUFD4"):
        raise SystemExit("BLS keyless Public Data API returned no PPI observations")
    if not bls_probe.get(us_phase2.JOLTS_SERIES["openings"]):
        raise SystemExit("BLS keyless Public Data API returned no JOLTS observations")
    print(
        "BLS Public Data API: ok "
        f"({len(bls_probe['CUUR0000SA0'])} CPI, "
        f"{len(bls_probe['WPUFD4'])} PPI, "
        f"{len(bls_probe[us_phase2.JOLTS_SERIES['openings']])} JOLTS observations)"
    )

    eci_probe = us_phase2._bls_quarter_observations(
        [us_phase2.ECI_SERIES["comp_qoq"]], now, "ci-eci-api"
    ).get(us_phase2.ECI_SERIES["comp_qoq"], [])
    if not eci_probe:
        raise SystemExit("BLS keyless Public Data API returned no ECI observations")
    print(f"BLS ECI API: ok ({len(eci_probe)} quarterly observations)")

    rich = [
        event for event in macro
        if event.provider in {
            "official-us-bls-cpi",
            "official-us-bls-ppi",
            "official-us-bls-nfp",
            "official-us-bea-pce",
            "official-us-bls-jolts",
            "official-us-bls-eci",
            "official-us-census-retail",
            "official-us-dol-claims",
        }
        and getattr(event, "metrics", ())
    ]
    if not rich:
        raise SystemExit("No high-signal US release carried a metrics bundle")

    te_events = [event for event in macro if "tradingeconomics" in event.provider.lower()]
    if te_events:
        raise SystemExit(f"Trading Economics leaked into official macro path: {len(te_events)} event(s)")

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
        raise SystemExit("NVIDIA official IR earnings anchor missing or shifted")
    print("NVIDIA official IR anchor: ok (2026-08-27 04:20 TPE)")

    print(f"official backend smoke check passed: {len(macro)} macro event(s) in the 35-day CI horizon")


if __name__ == "__main__":
    main()
