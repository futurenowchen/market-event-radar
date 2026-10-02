from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as official


def main() -> None:
    token = f"kr-cpi-live-{datetime.now(official.TPE):%Y%m%d%H%M%S}"
    actual, previous = official._kr_latest_result("cpi", token)
    if not actual:
        raise SystemExit("KR CPI live probe FAIL: latest official Actual is blank")
    if not previous:
        raise SystemExit("KR CPI live probe FAIL: immediately preceding official Previous is blank")
    print(f"KR CPI live probe PASS: actual={actual}, previous={previous}")


if __name__ == "__main__":
    main()
