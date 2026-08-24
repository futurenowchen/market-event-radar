from __future__ import annotations

from dataclasses import replace

import v2_event_official as official


_ORIGINAL_IMMEDIATE_FALLBACKS = official._immediate_fallbacks


def _normalized_immediate_fallbacks(start, end):
    events = []
    for event in _ORIGINAL_IMMEDIATE_FALLBACKS(start, end):
        if event.provider == "official-kr-bok":
            event = replace(event, category="央行事件")
        if event.event_id == "jh-2026-08-27-29":
            event = replace(
                event,
                title="傑克森霍爾全球央行年會（Jackson Hole，8/27–29，時間未定）",
            )
        events.append(event)
    return events


official._immediate_fallbacks = _normalized_immediate_fallbacks
