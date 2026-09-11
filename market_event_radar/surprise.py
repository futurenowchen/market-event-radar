from __future__ import annotations

from dataclasses import dataclass
import re

from .consensus import ConsensusObservation


@dataclass(frozen=True)
class SurpriseRule:
    semantic_family: str
    positive_direction: str
    negative_direction: str
    positive_impulse: str
    negative_impulse: str
    positive_policy: str
    negative_policy: str
    medium_threshold: float
    large_threshold: float


@dataclass(frozen=True)
class SurpriseResult:
    event_family: str
    metric_id: str
    actual: str
    consensus: str
    surprise: float
    surprise_unit: str
    direction: str
    magnitude: str
    impulse: str
    policy_implication: str
    provider: str


def _inflation_rule() -> SurpriseRule:
    return SurpriseRule(
        "inflation",
        "HOTTER_THAN_EXPECTED",
        "COOLER_THAN_EXPECTED",
        "inflation_up",
        "inflation_down",
        "HAWKISH",
        "DOVISH",
        0.1,
        0.2,
    )


def _growth_rule() -> SurpriseRule:
    return SurpriseRule(
        "growth",
        "STRONGER_THAN_EXPECTED",
        "WEAKER_THAN_EXPECTED",
        "growth_up",
        "growth_down",
        "HAWKISH",
        "DOVISH",
        0.2,
        0.5,
    )


_RULES: dict[tuple[str, str], SurpriseRule] = {}
for event_family in ("cpi", "ppi", "pce"):
    for metric_id in ("headline_yoy", "headline_mom", "core_yoy", "core_mom"):
        _RULES[(event_family, metric_id)] = _inflation_rule()

_RULES.update(
    {
        ("nfp", "payroll_change"): SurpriseRule(
            "labor",
            "STRONGER_THAN_EXPECTED",
            "WEAKER_THAN_EXPECTED",
            "labor_tightness",
            "labor_weakness",
            "HAWKISH",
            "DOVISH",
            50.0,
            100.0,
        ),
        ("nfp", "unemployment_rate"): SurpriseRule(
            "labor",
            "WEAKER_THAN_EXPECTED",
            "STRONGER_THAN_EXPECTED",
            "labor_weakness",
            "labor_tightness",
            "DOVISH",
            "HAWKISH",
            0.1,
            0.2,
        ),
        ("nfp", "avg_hourly_earnings_mom"): SurpriseRule(
            "wages",
            "HOTTER_THAN_EXPECTED",
            "COOLER_THAN_EXPECTED",
            "wage_pressure_up",
            "wage_pressure_down",
            "HAWKISH",
            "DOVISH",
            0.1,
            0.2,
        ),
        ("nfp", "avg_hourly_earnings_yoy"): SurpriseRule(
            "wages",
            "HOTTER_THAN_EXPECTED",
            "COOLER_THAN_EXPECTED",
            "wage_pressure_up",
            "wage_pressure_down",
            "HAWKISH",
            "DOVISH",
            0.1,
            0.2,
        ),
        ("claims", "initial_claims"): SurpriseRule(
            "labor",
            "WEAKER_THAN_EXPECTED",
            "STRONGER_THAN_EXPECTED",
            "labor_weakness",
            "labor_tightness",
            "DOVISH",
            "HAWKISH",
            10.0,
            25.0,
        ),
        ("retail_sales", "headline_mom"): _growth_rule(),
        ("retail_sales", "headline_yoy"): _growth_rule(),
        ("eci", "compensation_qoq"): SurpriseRule(
            "wages",
            "HOTTER_THAN_EXPECTED",
            "COOLER_THAN_EXPECTED",
            "wage_pressure_up",
            "wage_pressure_down",
            "HAWKISH",
            "DOVISH",
            0.1,
            0.3,
        ),
        ("eci", "wages_qoq"): SurpriseRule(
            "wages",
            "HOTTER_THAN_EXPECTED",
            "COOLER_THAN_EXPECTED",
            "wage_pressure_up",
            "wage_pressure_down",
            "HAWKISH",
            "DOVISH",
            0.1,
            0.3,
        ),
        ("eci", "compensation_yoy"): SurpriseRule(
            "wages",
            "HOTTER_THAN_EXPECTED",
            "COOLER_THAN_EXPECTED",
            "wage_pressure_up",
            "wage_pressure_down",
            "HAWKISH",
            "DOVISH",
            0.1,
            0.3,
        ),
        ("eci", "wages_yoy"): SurpriseRule(
            "wages",
            "HOTTER_THAN_EXPECTED",
            "COOLER_THAN_EXPECTED",
            "wage_pressure_up",
            "wage_pressure_down",
            "HAWKISH",
            "DOVISH",
            0.1,
            0.3,
        ),
    }
)


def parse_numeric(value: str) -> tuple[float | None, str]:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None, ""
    multiplier = 1.0
    unit = ""
    upper = text.upper()
    if upper.endswith("K"):
        unit = "K"
        text = text[:-1]
    elif upper.endswith("M"):
        multiplier = 1000.0
        unit = "K"
        text = text[:-1]
    elif text.endswith("%"):
        unit = "ppt"
        text = text[:-1]
    text = re.sub(r"^[^0-9+\-.]*", "", text)
    try:
        return float(text) * multiplier, unit
    except ValueError:
        return None, unit


def _magnitude(abs_surprise: float, rule: SurpriseRule) -> str:
    if abs_surprise >= rule.large_threshold:
        return "LARGE"
    if abs_surprise >= rule.medium_threshold:
        return "MEDIUM"
    return "SMALL"


def evaluate_surprise(metric_id: str, actual: str, observation: ConsensusObservation) -> SurpriseResult | None:
    if not observation.eligible_for_surprise or observation.metric_id != metric_id:
        return None
    event_family = observation.event_family.strip().lower()
    rule = _RULES.get((event_family, metric_id))
    if rule is None:
        return None
    actual_num, actual_unit = parse_numeric(actual)
    consensus_num, consensus_unit = parse_numeric(observation.consensus)
    if actual_num is None or consensus_num is None:
        return None
    if actual_unit and consensus_unit and actual_unit != consensus_unit:
        return None
    delta = actual_num - consensus_num
    if abs(delta) < 1e-12:
        return SurpriseResult(
            event_family,
            metric_id,
            actual,
            observation.consensus,
            0.0,
            actual_unit or consensus_unit,
            "IN_LINE",
            "SMALL",
            "neutral",
            "NEUTRAL",
            observation.provider,
        )
    positive = delta > 0
    return SurpriseResult(
        event_family=event_family,
        metric_id=metric_id,
        actual=actual,
        consensus=observation.consensus,
        surprise=delta,
        surprise_unit=actual_unit or consensus_unit,
        direction=rule.positive_direction if positive else rule.negative_direction,
        magnitude=_magnitude(abs(delta), rule),
        impulse=rule.positive_impulse if positive else rule.negative_impulse,
        policy_implication=rule.positive_policy if positive else rule.negative_policy,
        provider=observation.provider,
    )


def supported_surprise_keys() -> tuple[tuple[str, str], ...]:
    return tuple(sorted(_RULES))


def supported_metric_ids() -> tuple[str, ...]:
    """Backward-compatible convenience list; semantics still require event_family."""
    return tuple(sorted({metric_id for _, metric_id in _RULES}))
