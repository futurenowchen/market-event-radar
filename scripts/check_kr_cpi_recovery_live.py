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
    listing = official._fetch_text(official.KR_CPI_LIST_URL, token)
    links = official._kr_cpi_release_links(listing, official.KR_CPI_LIST_URL)
    print(
        "KR CPI live diagnostics: "
        f"listing_len={len(listing)}, "
        f"contains_title={'소비자물가동향' in listing}, "
        f"resolved_links={len(links)}, "
        f"list_nos={','.join(links[:3]) if links else 'none'}"
    )
    newest_title = ""
    for text, _href in official._links(listing, official.KR_CPI_LIST_URL):
        normalized = " ".join(text.split())
        if "소비자물가동향" in normalized and "보도자료" not in normalized:
            newest_title = normalized
            break
    if not newest_title:
        raise SystemExit("KR CPI live probe FAIL: latest CPI title is not discoverable")
    if not links:
        raise SystemExit("KR CPI live probe FAIL: no official CPI detail links resolved")

    actual, previous = official._kr_latest_result("cpi", token)
    if not actual:
        raise SystemExit("KR CPI live probe FAIL: latest official Actual is blank")
    if not previous:
        raise SystemExit("KR CPI live probe FAIL: immediately preceding official Previous is blank")
    print(
        f"KR CPI live probe PASS: newest_title={newest_title}, "
        f"detail={links[0]}, actual={actual}, previous={previous}"
    )


if __name__ == "__main__":
    main()
