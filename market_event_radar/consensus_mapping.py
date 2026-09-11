from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsensusTarget:
    official_provider: str
    event_family: str
    metric_id: str
    country: str
    trading_economics_indicator: str
    evidence: str = "verified-public-calendar"


# Conservative v1 mapping. Add a target only when the provider's indicator
# semantics match the official metric, not merely because the labels look close.
# In particular, our PPI core series excludes food, energy AND trade services;
# TE's common Core PPI series excludes food and energy, so those core PPI rows
# are intentionally unmapped rather than silently comparing different concepts.
_TARGETS: tuple[ConsensusTarget, ...] = (
    ConsensusTarget("official-us-bls-cpi", "cpi", "headline_yoy", "united states", "Inflation Rate YoY"),
    ConsensusTarget("official-us-bls-cpi", "cpi", "headline_mom", "united states", "Inflation Rate MoM"),
    ConsensusTarget("official-us-bls-cpi", "cpi", "core_yoy", "united states", "Core Inflation Rate YoY"),
    ConsensusTarget("official-us-bls-cpi", "cpi", "core_mom", "united states", "Core Inflation Rate MoM"),
    ConsensusTarget("official-us-bls-ppi", "ppi", "headline_yoy", "united states", "Producer Prices Change"),
    ConsensusTarget("official-us-bls-ppi", "ppi", "headline_mom", "united states", "Producer Price Inflation MoM"),
    ConsensusTarget("official-us-bea-pce", "pce", "headline_yoy", "united states", "PCE Price Index YoY"),
    ConsensusTarget("official-us-bea-pce", "pce", "headline_mom", "united states", "PCE Price Index MoM"),
    ConsensusTarget("official-us-bea-pce", "pce", "core_yoy", "united states", "Core PCE Price Index YoY"),
    ConsensusTarget("official-us-bea-pce", "pce", "core_mom", "united states", "Core PCE Price Index MoM"),
    ConsensusTarget("official-us-bls-nfp", "nfp", "payroll_change", "united states", "Non Farm Payrolls"),
    ConsensusTarget("official-us-bls-nfp", "nfp", "unemployment_rate", "united states", "Unemployment Rate"),
    ConsensusTarget("official-us-bls-nfp", "nfp", "avg_hourly_earnings_mom", "united states", "Average Hourly Earnings MoM"),
    ConsensusTarget("official-us-bls-nfp", "nfp", "avg_hourly_earnings_yoy", "united states", "Average Hourly Earnings YoY"),
    ConsensusTarget("official-us-dol-claims", "claims", "initial_claims", "united states", "Initial Jobless Claims"),
    ConsensusTarget("official-us-census-retail", "retail_sales", "headline_mom", "united states", "Retail Sales MoM"),
    ConsensusTarget("official-us-census-retail", "retail_sales", "headline_yoy", "united states", "Retail Sales YoY"),
    ConsensusTarget("official-us-bls-eci", "eci", "compensation_qoq", "united states", "Employment Cost Index"),
)

_BY_KEY = {(target.official_provider, target.metric_id): target for target in _TARGETS}


def target_for(official_provider: str, metric_id: str) -> ConsensusTarget | None:
    return _BY_KEY.get((str(official_provider or "").strip(), str(metric_id or "").strip()))


def targets_for_provider(official_provider: str) -> tuple[ConsensusTarget, ...]:
    provider = str(official_provider or "").strip()
    return tuple(target for target in _TARGETS if target.official_provider == provider)


def all_targets() -> tuple[ConsensusTarget, ...]:
    return _TARGETS
