from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_event_radar.consensus_mapping import all_targets, target_for, targets_for_provider
from market_event_radar.surprise import supported_surprise_keys


def main() -> None:
    cpi = target_for("official-us-bls-cpi", "headline_mom")
    assert cpi is not None
    assert cpi.event_family == "cpi"
    assert cpi.trading_economics_indicator == "Inflation Rate MoM"

    retail = target_for("official-us-census-retail", "headline_mom")
    assert retail is not None
    assert retail.event_family == "retail_sales"
    assert retail.trading_economics_indicator == "Retail Sales MoM"
    assert retail.event_family != cpi.event_family

    claims = target_for("official-us-dol-claims", "initial_claims")
    assert claims is not None
    assert claims.trading_economics_indicator == "Initial Jobless Claims"

    eci = target_for("official-us-bls-eci", "compensation_qoq")
    assert eci is not None
    assert eci.trading_economics_indicator == "Employment Cost Index"

    # Our official core PPI definition excludes trade services in addition to
    # food/energy, so do not map it to TE's different Core PPI concept.
    assert target_for("official-us-bls-ppi", "core_yoy") is None
    assert target_for("official-us-bls-ppi", "core_mom") is None

    # Every mapped target must have a semantic rule before it can ever produce
    # a SurpriseResult. Mapping without semantics would be an unsafe half-state.
    semantic_keys = set(supported_surprise_keys())
    for target in all_targets():
        assert (target.event_family, target.metric_id) in semantic_keys, target

    assert len(targets_for_provider("official-us-bls-cpi")) == 4
    assert len(all_targets()) >= 15
    print(f"consensus mapping tests passed: {len(all_targets())} target(s)")


if __name__ == "__main__":
    main()
