"""Public Python interface for Market Event Radar."""

from .consensus import ConsensusObservation
from .feed import fetch_latest, load_snapshot
from .models import EventMetric, MarketEvent, RadarSnapshot
from .risk import RiskWindow, build_risk_windows, event_risk_level
from .surprise import SurpriseResult, evaluate_surprise, parse_numeric, supported_metric_ids

__all__ = [
    "ConsensusObservation",
    "EventMetric",
    "MarketEvent",
    "RadarSnapshot",
    "RiskWindow",
    "SurpriseResult",
    "build_risk_windows",
    "evaluate_surprise",
    "event_risk_level",
    "fetch_latest",
    "load_snapshot",
    "parse_numeric",
    "supported_metric_ids",
]
