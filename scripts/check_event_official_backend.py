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
import v2_event_company_ir as company_ir  # noqa: F401  # install official company IR fallbacks


def main() -> None:
    now = datetime.now(official.TPE)
    start = now - timedelta(hours=48)
    end = now + timedelta(days=21)
    macro, health = official.collect_official_macro(start, end, "ci-smoke")

    print("source_health:")
    for name, ok in sorted(health.items()):
        print(f"  {name}: {'ok' if ok else 'failed'}")

    print("live_schedule_reachability:")
    print(f"  bls_cpi: {'ok' if official._fetch_text(resilience.BLS_CPI_SCHEDULE_URL, 'ci-live') else 'fallback'}")
    print(f"  bls_ppi: {'ok' if official._fetch_text(us_high_signal.PPI_SCHEDULE_URL, 'ci-live') else 'fallback'}")
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
        "United States": ("us_bls", "us_bea", "us_fed"),
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

    bls_probe = official._bls_observations(["CUUR0000SA0", "WPUFD4"], now, "ci-bls-api")
    if not bls_probe.get("CUUR0000SA0"):
        raise SystemExit("BLS keyless Public Data API returned no CPI observations")
    if not bls_probe.get("WPUFD4"):
        raise SystemExit("BLS keyless Public Data API returned no PPI observations")
    print(
        "BLS Public Data API: ok "
        f"({len(bls_probe['CUUR0000SA0'])} CPI, {len(bls_probe['WPUFD4'])} PPI observations)"
    )

    rich = [
        event for event in macro
        if event.provider in {"official-us-bls-cpi", "official-us-bls-ppi", "official-us-bls-nfp", "official-us-bea-pce"}
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

    print(f"official backend smoke check passed: {len(macro)} macro event(s) in the 21-day CI horizon")


if __name__ == "__main__":
    main()
