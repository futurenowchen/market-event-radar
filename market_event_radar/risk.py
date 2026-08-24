from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from .models import MarketEvent

TPE = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class RiskWindow:
    time_tpe: datetime
    title: str
    tier: str
    importance: int
    events: tuple[MarketEvent, ...]


def build_risk_windows(
    events: Iterable[MarketEvent],
    hours: int = 36,
    *,
    now: datetime | None = None,
) -> list[RiskWindow]:
    now = now or datetime.now(TPE)
    horizon = now + timedelta(hours=hours)
    upcoming = sorted(
        [e for e in events if now <= e.time_tpe <= horizon and e.tier in {"S", "A"}],
        key=lambda e: e.time_tpe,
    )

    groups: list[list[MarketEvent]] = []
    for event in upcoming:
        if not groups or event.time_tpe - groups[-1][-1].time_tpe > timedelta(minutes=10):
            groups.append([event])
        else:
            groups[-1].append(event)

    tier_rank = {"S": 3, "A": 2, "B": 1}
    windows: list[RiskWindow] = []
    for group in groups:
        if len(group) == 1:
            title = group[0].title
        elif all(e.category in {"總體經濟", "央行事件"} for e in group):
            countries = {e.country for e in group if e.country}
            prefix = next(iter(countries)) if len(countries) == 1 else "跨市場"
            title = f"{prefix}重要數據組合"
        elif all(e.category == "企業財報" for e in group):
            title = "AI產業財報集中窗口"
        else:
            title = "重要事件集中窗口"

        top_tier = max((e.tier for e in group), key=lambda t: tier_rank.get(t, 0))
        windows.append(
            RiskWindow(
                time_tpe=group[0].time_tpe,
                title=title,
                tier=top_tier,
                importance=max(e.importance for e in group),
                events=tuple(group),
            )
        )
    return windows


def event_risk_level(
    events: Iterable[MarketEvent],
    hours: int = 36,
    *,
    now: datetime | None = None,
) -> tuple[str, int]:
    windows = build_risk_windows(events, hours, now=now)
    if not windows:
        return "LOW", 1
    s_windows = sum(1 for window in windows if window.tier == "S")
    if s_windows >= 2:
        return "HIGH", 3
    if s_windows >= 1 or len(windows) >= 3:
        return "ELEVATED", 2
    return "NORMAL", 1
