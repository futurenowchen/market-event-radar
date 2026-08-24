from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

from .models import RadarSnapshot

DEFAULT_FEED_URL = (
    "https://raw.githubusercontent.com/futurenowchen/market-event-radar/"
    "main/data/latest.json"
)
USER_AGENT = "market-event-radar/0.1 (+https://github.com/futurenowchen/market-event-radar)"


def load_snapshot(path: str | Path) -> RadarSnapshot:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("snapshot root must be a JSON object")
    return RadarSnapshot.from_dict(payload)


def fetch_latest(url: str = DEFAULT_FEED_URL, timeout: float = 10.0) -> RadarSnapshot:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("feed root must be a JSON object")
    return RadarSnapshot.from_dict(payload)
