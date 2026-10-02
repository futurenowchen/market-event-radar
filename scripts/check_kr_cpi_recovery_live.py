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
    kosis_links = official._kr_cpi_kosis_release_links(token)
    rss = official._kr_fetch_text(official.KR_CPI_RSS_URL, f"{token}-rss")
    rss_links = official._kr_cpi_rss_release_links(rss)
    listing = ""
    html_links = []
    if len(rss_links) < 2:
        listing = official._kr_fetch_text(official.KR_CPI_LIST_URL, token)
        html_links = official._kr_cpi_release_links(listing, official.KR_CPI_LIST_URL)
    links = []
    for link in [*kosis_links, *rss_links, *html_links]:
        if link not in links:
            links.append(link)
    print(
        "KR CPI live diagnostics: "
        f"kosis_links={len(kosis_links)}, "
        f"rss_len={len(rss)}, rss_links={len(rss_links)}, "
        f"listing_len={len(listing)}, html_links={len(html_links)}, "
        f"resolved={','.join(links[:3]) if links else 'none'}"
    )
    if not links:
        raise SystemExit("KR CPI live probe FAIL: no official CPI detail links resolved")

    actual, previous = official._kr_latest_result("cpi", token)
    if not actual:
        raise SystemExit("KR CPI live probe FAIL: latest official Actual is blank")
    if not previous:
        raise SystemExit("KR CPI live probe FAIL: immediately preceding official Previous is blank")
    print(
        f"KR CPI live probe PASS: detail={links[0]}, "
        f"actual={actual}, previous={previous}"
    )


if __name__ == "__main__":
    main()
