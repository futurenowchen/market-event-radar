from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v2_event_official as backend
import v2_event_official_taiwan_resilience as tw


def main() -> None:
    table = """
    <table>
      <tr><th>調整日期</th><th>重貼現率</th><th>擔保放款融通利率</th></tr>
      <tr><td>2026/9/18</td><td>2.125</td><td>2.5</td></tr>
      <tr><td>2024/3/22</td><td>2</td><td>2.375</td></tr>
      <tr><td>113/3/22</td><td>2</td><td>2.375</td></tr>
    </table>
    """
    rows = tw._parse_cbc_rate_rows(table)
    assert rows[0] == (date(2026, 9, 18), "2.125%")
    assert (date(2024, 3, 22), "2%") in rows
    assert tw._cbc_rate_before_meeting(rows, date(2026, 9, 17)) == "2%"
    assert tw._cbc_adjustment_near_meeting(rows, date(2026, 9, 17)) == "2.125%"

    hold = """
    <article>
      <div>發布日期：2026-09-17</div>
      <p>本行維持政策利率不變，重貼現率、擔保放款融通利率及短期融通利率
      分別維持年息2%、2.375%及4.25%。</p>
    </article>
    """
    assert tw._cbc_decision_matches_day(backend._plain_text(hold), date(2026, 9, 17))
    assert tw._parse_cbc_discount_rate_from_decision(hold) == "2%"
    assert tw._cbc_decision_holds_rate(hold)

    change = """
    <article>
      <div>115年9月17日</div>
      <p>本行調升政策利率，重貼現率調整為2.125％。</p>
    </article>
    """
    assert tw._cbc_decision_matches_day(backend._plain_text(change), date(2026, 9, 17))
    assert tw._parse_cbc_discount_rate_from_decision(change) == "2.125%"

    original = tw._ORIGINAL_TW_CBC_EVENTS
    original_fetch = backend._fetch_text
    original_links = backend._links
    try:
        event = backend._event(
            event_id="official-tw-cbc-2026-09-17",
            dt=datetime.fromisoformat("2026-09-17T16:30:00+08:00"),
            title="台灣中央銀行理監事會利率決議",
            country="台灣",
            tier="S",
            tags=("台灣", "央行", "利率"),
            source="中央銀行",
            source_url=backend.CBC_MEETING_URL,
            provider="official-tw-cbc",
        )

        def fake_events(start, end, token):
            del start, end, token
            return [event], True

        def fake_fetch(url, token):
            del token
            if url == tw.CBC_RATE_URL:
                return """
                <table>
                  <tr><th>調整日期</th><th>重貼現率</th></tr>
                  <tr><td>2024/3/22</td><td>2</td></tr>
                </table>
                """
            if url == backend.CBC_MEETING_URL:
                return '<a href="/tw/cp-test.html">中央銀行理監事聯席會議決議新聞稿</a>'
            if url.endswith("/tw/cp-test.html"):
                return hold
            return ""

        tw._ORIGINAL_TW_CBC_EVENTS = fake_events
        backend._fetch_text = fake_fetch
        backend._links = lambda html, base: [
            ("中央銀行理監事聯席會議決議新聞稿", "https://www.cbc.gov.tw/tw/cp-test.html")
        ]
        rows, ok = tw._tw_cbc_events_resilient(
            datetime.fromisoformat("2026-09-17T00:00:00+08:00"),
            datetime.fromisoformat("2026-09-18T00:00:00+08:00"),
            "test",
        )
        assert ok and len(rows) == 1
        assert rows[0].actual == "2%"
        assert rows[0].previous == "2%"
        assert rows[0].status == "released"
        assert rows[0].source_url.endswith("/tw/cp-test.html")
    finally:
        tw._ORIGINAL_TW_CBC_EVENTS = original
        backend._fetch_text = original_fetch
        backend._links = original_links

    print("Taiwan CBC resilience tests passed")


if __name__ == "__main__":
    main()
