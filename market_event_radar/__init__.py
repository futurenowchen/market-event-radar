"""Public Python interface for Market Event Radar."""

from .consensus import ConsensusObservation
from .feed import fetch_latest, load_snapshot
from .models import EventMetric, MarketEvent, RadarSnapshot
from .private_overlay import (
    PrivateOverlayObservation,
    VALUE_KIND_PROVIDER_FORECAST,
    VALUE_KIND_SURVEY_CONSENSUS,
    build_private_overlay,
    observation_from_dict,
    observations_from_mt5_canary,
)
from .risk import RiskWindow, build_risk_windows, event_risk_level
from .surprise import (
    SurpriseResult,
    evaluate_surprise,
    parse_numeric,
    supported_metric_ids,
    supported_surprise_keys,
)

__all__ = [
    "ConsensusObservation",
    "EventMetric",
    "MarketEvent",
    "PrivateOverlayObservation",
    "RadarSnapshot",
    "RiskWindow",
    "SurpriseResult",
    "VALUE_KIND_PROVIDER_FORECAST",
    "VALUE_KIND_SURVEY_CONSENSUS",
    "build_private_overlay",
    "build_risk_windows",
    "evaluate_surprise",
    "event_risk_level",
    "fetch_latest",
    "load_snapshot",
    "observation_from_dict",
    "observations_from_mt5_canary",
    "parse_numeric",
    "supported_metric_ids",
    "supported_surprise_keys",
]
