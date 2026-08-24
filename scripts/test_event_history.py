from __future__ import annotations

import json
import tempfile
from pathlib import Path

from update_event_history import _load_jsonl, update_history


def _write_snapshot(path: Path, generated_at: str, *, actual: str = "", forecast: str = "2.8%") -> None:
    payload = {
        "schema_version": 2,
        "generated_at_tpe": generated_at,
        "events": [
            {
                "event_id": "official-test-cpi-20260824",
                "time_tpe": "2026-08-24T20:30:00+08:00",
                "title": "Test CPI",
                "category": "總體經濟",
                "importance": 3,
                "tier": "S",
                "country": "美國",
                "market_tags": ["CPI", "Fed"],
                "actual": actual,
                "forecast": forecast,
                "previous": "2.9%",
                "source": "Official Test Source",
                "source_url": "https://example.com/official",
                "status": "released" if actual else "scheduled",
                "expects_result": True,
                "provider": "official-test",
                "symbol": "",
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        snapshot = root / "latest.json"
        history = root / "history"

        _write_snapshot(snapshot, "2026-08-24T15:00:00+08:00")
        ledger, count = update_history(snapshot, history)
        assert count == 1
        assert _load_jsonl(ledger)[0]["change_type"] == "first_seen"

        _write_snapshot(snapshot, "2026-08-24T15:15:00+08:00")
        _, count = update_history(snapshot, history)
        assert count == 0

        _write_snapshot(snapshot, "2026-08-24T15:30:00+08:00", forecast="3.0%")
        _, count = update_history(snapshot, history)
        assert count == 1
        assert _load_jsonl(ledger)[-1]["change_type"] == "forecast_changed"

        _write_snapshot(snapshot, "2026-08-24T20:35:00+08:00", actual="3.1%", forecast="3.0%")
        _, count = update_history(snapshot, history)
        assert count == 1
        assert _load_jsonl(ledger)[-1]["change_type"] == "released"

        _write_snapshot(snapshot, "2026-08-24T21:00:00+08:00", actual="3.2%", forecast="3.0%")
        _, count = update_history(snapshot, history)
        assert count == 1
        assert _load_jsonl(ledger)[-1]["change_type"] == "revision"

        assert len(_load_jsonl(ledger)) == 4
        print("event history ledger tests passed")


if __name__ == "__main__":
    main()
