from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as official
from scripts import refresh_gate


TPE = timezone(timedelta(hours=8))




def test_kr_cpi_rss_resolves_current_and_previous_release_links() -> None:
    rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
      <item>
        <title>2026년 9월 소비자물가동향</title>
        <link>https://mods.go.kr/board.es?act=view&amp;bid=213&amp;list_no=447322&amp;mid=a10301040100</link>
      </item>
      <item>
        <title>2026년 8월 소비자물가동향</title>
        <link>https://mods.go.kr/board.es?act=view&amp;bid=213&amp;list_no=446746&amp;mid=a10301040100</link>
      </item>
    </channel></rss>"""
    assert official._kr_cpi_rss_release_links(rss) == [
        "https://www.mods.go.kr/board.es?act=view&bid=213&list_no=447322&mid=a10301040100",
        "https://www.mods.go.kr/board.es?act=view&bid=213&list_no=446746&mid=a10301040100",
    ]


def test_kr_fetch_retries_after_cached_empty_response() -> None:
    original = official._fetch_text
    calls = []

    def fake_fetch(url: str, token: str) -> str:
        calls.append((url, token))
        return "" if len(calls) == 1 else "<html>ok</html>"

    official._fetch_text = fake_fetch
    try:
        result = official._kr_fetch_text("https://mods.example/test", "probe", attempts=3)
    finally:
        official._fetch_text = original

    assert result == "<html>ok</html>"
    assert [token for _url, token in calls] == ["probe", "probe-retry-1"]


def test_kr_cpi_latest_uses_two_official_releases() -> None:
    assert "bid=213" in official.KR_CPI_LIST_URL

    listing = """
    <html><body>
      <li>
        <strong>2026년 9월 소비자물가동향</strong>
        <a href="/attachPreview.es?bid=213&list_no=447322&seq=2">미리보기</a>
      </li>
      <li>
        <strong>2026년 8월 소비자물가동향</strong>
        <a href="/attachPreview.es?bid=213&list_no=446746&seq=2">미리보기</a>
      </li>
    </body></html>
    """
    current = "9월 소비자물가지수는 전월대비 0.3%, 전년동월대비 2.9% 각각 상승"
    previous = "8월 소비자물가지수는 전월대비 0.1%, 전년동월대비 2.0% 각각 상승"

    original = official._fetch_text

    def fake_fetch(url: str, _token: str) -> str:
        if "list_no=447322" in url:
            return current
        if "list_no=446746" in url:
            return previous
        if "bid=213" in url:
            return listing
        return ""

    official._fetch_text = fake_fetch
    try:
        actual, prior = official._kr_latest_result("cpi", "test")
    finally:
        official._fetch_text = original

    assert actual == "2.9%"
    assert prior == "2%"


def test_kr_cpi_previous_fails_closed_with_one_release() -> None:
    listing = """
    <html><body>
      <strong>2026년 9월 소비자물가동향</strong>
      <a href="/attachPreview.es?bid=213&list_no=447322&seq=2">미리보기</a>
    </body></html>
    """
    current = "9월 소비자물가지수는 전월대비 0.3%, 전년동월대비 2.9% 각각 상승"

    original = official._fetch_text

    def fake_fetch(url: str, _token: str) -> str:
        if "list_no=447322" in url:
            return current
        return listing

    official._fetch_text = fake_fetch
    try:
        actual, prior = official._kr_latest_result("cpi", "test")
    finally:
        official._fetch_text = original

    assert actual == "2.9%"
    assert prior == ""




def test_kr_cpi_current_javascript_title_link_normalizes_to_detail_url() -> None:
    listing = """
    <ul>
      <li>
        <a href="javascript:addSearchParam('/board.es?mid=a10301040200&bid=213&act=view&list_no=447322&tag=&nPage=1&ref_bid=');">
          새글 2026년 9월 소비자물가동향
        </a>
        <a href="/boardDownload.es?bid=213&list_no=447322&seq=2">
          2026년 9월 소비자물가동향(보도자료).pdf
        </a>
      </li>
      <li>
        <a href="javascript:addSearchParam('/board.es?mid=a10301040200&bid=213&act=view&list_no=446746&tag=&nPage=1&ref_bid=');">
          2026년 8월 소비자물가동향
        </a>
      </li>
    </ul>
    """
    links = official._kr_cpi_release_links(listing, official.KR_CPI_LIST_URL)
    assert links == [
        "https://www.mods.go.kr/board.es?act=view&bid=213&list_no=447322&mid=a10301040100",
        "https://www.mods.go.kr/board.es?act=view&bid=213&list_no=446746&mid=a10301040100",
    ]


def test_kr_cpi_current_listing_resolves_plain_title_preview_links() -> None:
    listing = """
    <ul>
      <li><span>2026년 9월 소비자물가동향</span>
          <a href="/attachPreview.es?bid=213&list_no=447322&seq=2">미리보기</a></li>
      <li><span>2026년 8월 소비자물가동향</span>
          <a href="/attachPreview.es?bid=213&list_no=446746&seq=2">미리보기</a></li>
    </ul>
    """
    links = official._kr_cpi_release_links(listing, official.KR_CPI_LIST_URL)
    assert links == [
        "https://www.mods.go.kr/board.es?act=view&bid=213&list_no=447322&mid=a10301040100",
        "https://www.mods.go.kr/board.es?act=view&bid=213&list_no=446746&mid=a10301040100",
    ]


def _snapshot(event_time: datetime) -> dict:
    return {
        "schema_version": 2,
        "snapshot_date_tpe": event_time.date().isoformat(),
        "official_macro_ready": True,
        "events": [
            {
                "event_id": "official-kr-mods-cpi-test",
                "title": "韓國消費者物價指數（CPI）",
                "time_tpe": event_time.isoformat(),
                "expects_result": True,
                "actual": "",
            }
        ],
    }


def test_refresh_gate_retries_missing_result_inside_48h() -> None:
    event_time = datetime(2026, 10, 2, 7, 0, tzinfo=TPE)
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "latest.json"
        payload = _snapshot(event_time)
        payload["snapshot_date_tpe"] = "2026-10-02"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        mode, reason = refresh_gate.decide(
            path,
            False,
            now=event_time + timedelta(hours=13),
        )
    assert mode == "smart"
    assert "missing actual value" in reason


def test_refresh_gate_stops_after_retention_window() -> None:
    event_time = datetime(2026, 10, 2, 7, 0, tzinfo=TPE)
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "latest.json"
        payload = _snapshot(event_time)
        payload["snapshot_date_tpe"] = "2026-10-04"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        mode, _ = refresh_gate.decide(
            path,
            False,
            now=event_time + timedelta(hours=49),
        )
    assert mode == "none"


def main() -> None:
    tests = [
        test_kr_cpi_rss_resolves_current_and_previous_release_links,
        test_kr_fetch_retries_after_cached_empty_response,
        test_kr_cpi_latest_uses_two_official_releases,
        test_kr_cpi_previous_fails_closed_with_one_release,
        test_kr_cpi_current_javascript_title_link_normalizes_to_detail_url,
        test_kr_cpi_current_listing_resolves_plain_title_preview_links,
        test_refresh_gate_retries_missing_result_inside_48h,
        test_refresh_gate_stops_after_retention_window,
    ]
    for test in tests:
        test()
    print(f"KR CPI recovery regression PASS: {len(tests)} tests")


if __name__ == "__main__":
    main()
