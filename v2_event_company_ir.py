from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import v2_event_official as official
import v2_event_radar as core


NVIDIA_IR_URL = (
    "https://investor.nvidia.com/news/press-release-details/2026/"
    "NVIDIA-Sets-Conference-Call-for-Second-Quarter-Financial-Results/default.aspx"
)

# Company IR announcements are authoritative for whether a major earnings event
# exists and when it happens. Market-data providers are enrichment sources only.
# Add future S-tier official announcements here after the company publishes them.
OFFICIAL_IR_EVENTS: tuple[core.MarketEvent, ...] = (
    core.MarketEvent(
        event_id="official-ir-nvda-2026-08-27-q2fy27",
        time_tpe=datetime(2026, 8, 27, 4, 20, tzinfo=core.TPE),
        title="輝達（NVIDIA）FY2027第二季財報公布",
        category="企業財報",
        importance=3,
        tier="S",
        market_tags=("AI", "GPU", "半導體", "台積電", "台指"),
        source="NVIDIA Investor Relations",
        source_url=NVIDIA_IR_URL,
        status="scheduled",
        expects_result=True,
        provider="official-company-ir",
        symbol="NVDA",
    ),
)

_ORIGINAL_COMPANY_EVENTS = official._company_events
_ORIGINAL_SMART_REFRESH_MISSING = official.smart_refresh_missing


def official_ir_events(start: datetime, end: datetime) -> list[core.MarketEvent]:
    return [event for event in OFFICIAL_IR_EVENTS if start <= event.time_tpe <= end]


def _matching_market_event(
    official_event: core.MarketEvent,
    market_events: list[core.MarketEvent],
) -> core.MarketEvent | None:
    candidates = [
        event
        for event in market_events
        if event.symbol == official_event.symbol
        and abs(event.time_tpe - official_event.time_tpe) <= timedelta(hours=48)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda event: abs(event.time_tpe - official_event.time_tpe))


def merge_official_ir_events(
    market_events: list[core.MarketEvent],
    start: datetime,
    end: datetime,
) -> list[core.MarketEvent]:
    merged: list[core.MarketEvent] = []
    consumed_ids: set[str] = set()

    for ir_event in official_ir_events(start, end):
        market_event = _matching_market_event(ir_event, market_events)
        if market_event is None:
            merged.append(ir_event)
            continue

        consumed_ids.add(market_event.event_id)
        merged.append(
            replace(
                ir_event,
                actual=market_event.actual,
                forecast=market_event.forecast,
                previous=market_event.previous,
                status="released" if market_event.actual else "scheduled",
            )
        )

    merged.extend(event for event in market_events if event.event_id not in consumed_ids)
    return core._dedupe(merged)


def _company_events_with_ir(
    start: datetime,
    end: datetime,
    refresh_token: str,
) -> list[core.MarketEvent]:
    market_events = _ORIGINAL_COMPANY_EVENTS(start, end, refresh_token)
    return merge_official_ir_events(market_events, start, end)


def _smart_refresh_missing_with_ir(
    events: list[core.MarketEvent],
    now: datetime | None = None,
) -> list[core.MarketEvent]:
    now = now or datetime.now(core.TPE)
    refreshed = _ORIGINAL_SMART_REFRESH_MISSING(events, now)

    due_ir = [
        event
        for event in events
        if event.provider == "official-company-ir"
        and event.expects_result
        and not event.actual
        and now >= event.time_tpe + timedelta(minutes=5)
        and now - event.time_tpe <= timedelta(hours=12)
    ]
    if not due_ir:
        return refreshed

    token = f"official-ir-smart-{now:%Y%m%d-%H%M}"
    company_rows = _company_events_with_ir(
        now - timedelta(days=1),
        now + timedelta(days=1),
        token,
    )
    return core._dedupe([*refreshed, *company_rows])


def install() -> None:
    # Idempotent monkeypatch: importing this module is enough to strengthen the
    # official backend without duplicating the large macro-source implementation.
    official._company_events = _company_events_with_ir
    official.smart_refresh_missing = _smart_refresh_missing_with_ir


install()
