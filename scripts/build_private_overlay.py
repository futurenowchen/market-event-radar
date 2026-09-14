from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_event_radar.private_overlay import (
    build_private_overlay,
    observation_from_dict,
    observations_from_mt5_canary,
)


def _load(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a private consensus/surprise overlay without modifying the public radar snapshot."
    )
    parser.add_argument("--snapshot", default="data/latest.json")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--mt5-canary", help="MT5 private canary report JSON")
    source.add_argument("--observations", help="Normalized private observation bundle JSON")
    parser.add_argument("--output", required=True, help="Private/local overlay JSON path")
    args = parser.parse_args()

    snapshot = _load(args.snapshot)
    if args.mt5_canary:
        observations = observations_from_mt5_canary(_load(args.mt5_canary))
    else:
        bundle = _load(args.observations)
        raw_rows = bundle.get("observations", [])
        if not isinstance(raw_rows, list):
            raise ValueError("observations bundle must contain an observations array")
        observations = [observation_from_dict(row) for row in raw_rows if isinstance(row, dict)]

    overlay = build_private_overlay(snapshot, observations)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(overlay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(output),
                "observation_count": overlay["observation_count"],
                "canonical_surprise_count": overlay["canonical_surprise_count"],
                "diagnostic_comparison_count": overlay["diagnostic_comparison_count"],
                "skipped_count": len(overlay["skipped"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
