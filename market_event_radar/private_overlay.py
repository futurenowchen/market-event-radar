from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .consensus import ConsensusObservation
from .surprise import SurpriseResult, evaluate_surprise


OVERLAY_SCHEMA_VERSION = 1
VALUE_KIND_SURVEY_CONSENSUS = "survey_consensus"
VALUE_KIND_PROVIDER_FORECAST = "provider_forecast"
_ALLOWED_VALUE_KINDS = {VALUE_KIND_SURVEY_CONSENSUS, VALUE_KIND_PROVIDER_FORECAST}


@dataclass(frozen=True)
class PrivateOverlayObservation:
    official_event_id: str
    official_provider: str
    event_family: str
    metric_id: str
    value: str
    value_kind: str
    provider: str
    captured_at: datetime
    release_time: datetime
    provider_event_id: str = ""
    provider_value_id: str = ""
    unit: str = ""
    source_url: str = ""
    evidence: str = ""

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None or self.release_time.tzinfo is None:
            raise ValueError("captured_at and release_time must be timezone-aware")
        if self.value_kind not in _ALLOWED_VALUE_KINDS:
            raise ValueError(f"unsupported value_kind: {self.value_kind}")
        for field_name in ("official_event_id", "event_family", "metric_id", "provider"):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"{field_name} is required")

    @property
    def captured_before_release(self) -> bool:
        return bool(self.value.strip()) and self.captured_at < self.release_time

    @property
    def eligible_for_canonical_surprise(self) -> bool:
        return self.value_kind == VALUE_KIND_SURVEY_CONSENSUS and self.captured_before_release

    def to_dict(self) -> dict[str, Any]:
        return {
            "official_event_id": self.official_event_id,
            "official_provider": self.official_provider,
            "event_family": self.event_family,
            "metric_id": self.metric_id,
            "value": self.value,
            "value_kind": self.value_kind,
            "provider": self.provider,
            "provider_event_id": self.provider_event_id,
            "provider_value_id": self.provider_value_id,
            "captured_at": self.captured_at.isoformat(),
            "release_time": self.release_time.isoformat(),
            "unit": self.unit,
            "source_url": self.source_url,
            "evidence": self.evidence,
            "captured_before_release": self.captured_before_release,
            "eligible_for_canonical_surprise": self.eligible_for_canonical_surprise,
        }


def _parse_iso(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("datetime value is required")
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return dt.astimezone(timezone.utc)


def observation_from_dict(payload: dict[str, Any]) -> PrivateOverlayObservation:
    return PrivateOverlayObservation(
        official_event_id=str(payload.get("official_event_id") or "").strip(),
        official_provider=str(payload.get("official_provider") or "").strip(),
        event_family=str(payload.get("event_family") or "").strip().lower(),
        metric_id=str(payload.get("metric_id") or "").strip(),
        value=str(payload.get("value") or "").strip(),
        value_kind=str(payload.get("value_kind") or "").strip(),
        provider=str(payload.get("provider") or "").strip(),
        provider_event_id=str(payload.get("provider_event_id") or "").strip(),
        provider_value_id=str(payload.get("provider_value_id") or "").strip(),
        captured_at=_parse_iso(payload.get("captured_at")),
        release_time=_parse_iso(payload.get("release_time")),
        unit=str(payload.get("unit") or "").strip(),
        source_url=str(payload.get("source_url") or "").strip(),
        evidence=str(payload.get("evidence") or "").strip(),
    )


def observations_from_mt5_canary(report: dict[str, Any]) -> list[PrivateOverlayObservation]:
    """Normalize an MT5 canary report into private provider-forecast observations.

    MT5 values intentionally remain `provider_forecast`. This adapter must never
    promote them to `survey_consensus` merely because the provider field is named
    Forecast in MetaTrader.
    """

    observations: list[PrivateOverlayObservation] = []
    for row in report.get("results", []):
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "") != "MATCHED":
            continue
        value = str(row.get("provider_forecast") or "").strip()
        event_id = str(row.get("official_event_id") or "").strip()
        if not value or not event_id:
            continue
        observations.append(
            PrivateOverlayObservation(
                official_event_id=event_id,
                official_provider=str(row.get("official_provider") or "").strip(),
                event_family=str(row.get("event_family") or "").strip().lower(),
                metric_id=str(row.get("metric_id") or "").strip(),
                value=value,
                value_kind=VALUE_KIND_PROVIDER_FORECAST,
                provider=str(row.get("provider") or report.get("provider") or "").strip(),
                provider_event_id=str(row.get("provider_event_id") or "").strip(),
                provider_value_id=str(row.get("provider_value_id") or "").strip(),
                captured_at=_parse_iso(row.get("captured_at")),
                release_time=_parse_iso(row.get("release_time")),
                unit=str(row.get("unit") or "").strip(),
                source_url=str(row.get("source_url") or "").strip(),
                evidence="mt5-private-canary",
            )
        )
    return observations


def _event_index(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(event.get("event_id") or "").strip(): event
        for event in snapshot.get("events", [])
        if isinstance(event, dict) and str(event.get("event_id") or "").strip()
    }


def _metric_from_event(event: dict[str, Any], metric_id: str) -> dict[str, Any] | None:
    for metric in event.get("metrics", []):
        if isinstance(metric, dict) and str(metric.get("metric_id") or "").strip() == metric_id:
            return metric
    return None


def _comparison_result(actual: str, observation: PrivateOverlayObservation) -> SurpriseResult | None:
    if not observation.captured_before_release:
        return None
    proxy = ConsensusObservation(
        event_key=observation.official_event_id,
        event_family=observation.event_family,
        metric_id=observation.metric_id,
        consensus=observation.value,
        provider=observation.provider,
        provider_event_id=observation.provider_event_id,
        fetched_at=observation.captured_at,
        as_of=observation.captured_at,
        release_time=observation.release_time,
        unit=observation.unit,
        source_url=observation.source_url,
        raw_value=observation.value,
    )
    return evaluate_surprise(observation.metric_id, actual, proxy)


def _result_to_dict(result: SurpriseResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "event_family": result.event_family,
        "metric_id": result.metric_id,
        "actual": result.actual,
        "reference_value": result.consensus,
        "difference": result.surprise,
        "difference_unit": result.surprise_unit,
        "direction": result.direction,
        "magnitude": result.magnitude,
        "impulse": result.impulse,
        "policy_implication": result.policy_implication,
        "provider": result.provider,
    }


def build_private_overlay(
    snapshot: dict[str, Any],
    observations: Iterable[PrivateOverlayObservation],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a private overlay without mutating the official public snapshot.

    Survey consensus may create `canonical_surprise`. Generic provider forecasts
    (including MT5) may only create `diagnostic_comparison`.
    """

    event_by_id = _event_index(snapshot)
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for observation in observations:
        event = event_by_id.get(observation.official_event_id)
        if event is None:
            skipped.append({
                "official_event_id": observation.official_event_id,
                "metric_id": observation.metric_id,
                "reason": "official_event_missing",
            })
            continue
        if observation.official_provider and str(event.get("provider") or "").strip() != observation.official_provider:
            skipped.append({
                "official_event_id": observation.official_event_id,
                "metric_id": observation.metric_id,
                "reason": "official_provider_mismatch",
            })
            continue
        metric = _metric_from_event(event, observation.metric_id)
        if metric is None:
            skipped.append({
                "official_event_id": observation.official_event_id,
                "metric_id": observation.metric_id,
                "reason": "official_metric_missing",
            })
            continue

        actual = str(metric.get("actual") or "").strip()
        comparison = _comparison_result(actual, observation) if actual else None
        canonical = comparison if observation.eligible_for_canonical_surprise else None
        diagnostic = comparison if observation.value_kind == VALUE_KIND_PROVIDER_FORECAST else None

        rows.append(
            {
                **observation.to_dict(),
                "official_title": str(event.get("title") or "").strip(),
                "official_time_tpe": str(event.get("time_tpe") or "").strip(),
                "official_status": str(event.get("status") or "").strip(),
                "official_actual": actual,
                "official_previous": str(metric.get("previous") or "").strip(),
                "official_unit": str(metric.get("unit") or "").strip(),
                "canonical_surprise": _result_to_dict(canonical),
                "diagnostic_comparison": _result_to_dict(diagnostic),
            }
        )

    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")

    return {
        "schema_version": OVERLAY_SCHEMA_VERSION,
        "overlay_kind": "private-consensus-surprise",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "source_snapshot_schema_version": snapshot.get("schema_version"),
        "source_snapshot_generated_at_tpe": snapshot.get("generated_at_tpe", ""),
        "observation_count": len(rows),
        "canonical_surprise_count": sum(row["canonical_surprise"] is not None for row in rows),
        "diagnostic_comparison_count": sum(row["diagnostic_comparison"] is not None for row in rows),
        "observations": rows,
        "skipped": skipped,
    }
