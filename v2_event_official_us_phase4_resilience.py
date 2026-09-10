from __future__ import annotations

import re

import v2_event_official_us_phase4 as phase4


def _is_current_chair_text(text: str) -> bool:
    """Match Chair/Chairman titles case-insensitively while excluding Vice Chairs."""
    lower = str(text or "").lower()
    if "vice chair" in lower or "vice chairman" in lower:
        return False
    return bool(re.search(r"\b(?:chair|chairman)\s+[A-Z]", str(text or ""), re.I))


def install() -> None:
    phase4._is_current_chair_text = _is_current_chair_text


install()
