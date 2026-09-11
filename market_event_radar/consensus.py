from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ConsensusObservation:
    event_key: str
    metric_id: str
    consensus: str
    provider: str
    fetched_at: datetime
    release_time: datetime
    event_family: str = ""
    provider_event_id: str = ""
    as_of: datetime | None = None
    unit: str = ""
    source_url: str = ""
    raw_value: str = ""

    def __post_init__(self) -> None:
        if self.fetched_at.tzinfo is None or self.release_time.tzinfo is None:
            raise ValueError("fetched_at and release_time must be timezone-aware")
        if self.as_of is not None and self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware when provided")
        if not self.provider.strip():
            raise ValueError("provider is required")
        if not self.metric_id.strip():
            raise ValueError("metric_id is required")

    @property
    def effective_as_of(self) -> datetime:
        return self.as_of or self.fetched_at

    @property
    def eligible_for_surprise(self) -> bool:
        """Only information known strictly before release may drive surprise."""
        return bool(self.consensus.strip()) and self.effective_as_of < self.release_time

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_key": self.event_key,
            "event_family": self.event_family,
            "metric_id": self.metric_id,
            "consensus": self.consensus,
            "provider": self.provider,
            "provider_event_id": self.provider_event_id,
            "fetched_at": self.fetched_at.isoformat(),
            "as_of": self.as_of.isoformat() if self.as_of else "",
            "release_time": self.release_time.isoformat(),
            "unit": self.unit,
            "source_url": self.source_url,
            "raw_value": self.raw_value,
            "eligible_for_surprise": self.eligible_for_surprise,
        }
