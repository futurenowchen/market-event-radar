from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta
from html import unescape
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import streamlit as st

import v2_event_radar as core

TPE = core.TPE
NY = ZoneInfo("America/New_York")
JST = ZoneInfo("Asia/Tokyo")
KST = ZoneInfo("Asia/Seoul")

USER_AGENT = "NA-Command-Center/2.2 (+https://github.com/futurenowchen/market-event-radar)"

BLS_ICS_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BEA_SCHEDULE_URL = "https://www.bea.gov/news/schedule"
BEA_RELEASES_URL = "https://www.bea.gov/news/current-releases"
FED_FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FED_PRESS_BASE = "https://www.federalreserve.gov/newsevents/pressreleases/monetary"

TW_CPI_SCHEDULE_URL = (
    "https://www.stat.gov.tw/News_NoticeCalendar.aspx?Dept=4527&"
    "_Query=%E6%B6%88%E8%B2%BB%E8%80%85%E7%89%A9%E5%83%B9%E6%8C%87%E6%95%B8&n=3717"
)
TW_GDP_SCHEDULE_URL = (
    "https://www.stat.gov.tw/News_NoticeCalendar.aspx?Dept=4527&"
    "_Query=%E5%9C%8B%E6%B0%91%E6%89%80%E5%BE%97&n=3717"
)
TW_NEWS_URL = "https://www.stat.gov.tw/News.aspx?PageSize=200&_CSN=130&n=3703&sms=10980"
CBC_MEETING_URL = "https://www.cbc.gov.tw/tw/lp-357-1-1-60.html"
CBC_HOME_URL = "https://www.cbc.gov.tw/"

JP_CPI_SCHEDULE_URL = "https://www.stat.go.jp/english/data/cpi/1582.htm"
JP_CPI_HOME_URL = "https://www.stat.go.jp/english/data/cpi/"
JP_GDP_SCHEDULE_URL = "https://www.esri.cao.go.jp/en/sna/kouhyou/kouhyou_top.html"
BOJ_MPM_URL = "https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm"
BOJ_STATEMENTS_URL = "https://www.boj.or.jp/en/mopo/mpmdeci/state_2026/index.htm"

KR_RELEASE_PLAN_URL = "https://mods.go.kr/schedule.es?mid=a10308010000"
KR_CPI_LIST_URL = (
    "https://mods.go.kr/board.es?mid=a10301040100&bid=a103010401&"
    "ref_bid=213,215,214,11860,11695"
)
KR_INDUSTRY_LIST_URL = "https://mods.go.kr/board.es?mid=a10301050100&bid=216"
BOK_POLICY_DATES_URL = "https://www.bok.or.kr/portal/singl/crncyPolicyDrcMtg/listYear.do?menuNo=200755&mtgSe=A"
BOK_HOME_URL = "https://www.bok.or.kr/eng/main/main.do"


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            text = " ".join("".join(self._cell).split())
            self._row.append(text)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(cell for cell in self._row):
                self.rows.append(self._row)
            self._row = None
            self._cell = None


class _LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "a":
            attrs_dict = dict(attrs)
            self._href = attrs_dict.get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            text = " ".join("".join(self._text).split())
            self.links.append((text, urljoin(self.base_url, self._href)))
            self._href = None
            self._text = []


@st.cache_data(ttl=900, show_spinner=False)
def _fetch_text(url: str, refresh_token: str = "") -> str:
    del refresh_token
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,*/*"})
    try:
        with urlopen(req, timeout=12) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
    except Exception:
        return ""
    for encoding in (charset, "utf-8", "cp950", "euc-kr"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


@st.cache_data(ttl=900, show_spinner=False)
def _post_json(url: str, payload: dict, refresh_token: str = "") -> dict:
    del refresh_token
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _plain_text(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"(?is)<script.*?>.*?</script>|<style.*?>.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return " ".join(unescape(text).split())


def _table_rows(html: str) -> list[list[str]]:
    parser = _TableParser()
    try:
        parser.feed(html)
    except Exception:
        return []
    return parser.rows


def _links(html: str, base_url: str) -> list[tuple[str, str]]:
    parser = _LinkParser(base_url)
    try:
        parser.feed(html)
    except Exception:
        return []
    return parser.links


def _dt_local(day: date, hh: int, mm: int, tz) -> datetime:
    return datetime.combine(day, time(hh, mm), tzinfo=tz).astimezone(TPE)


def _in_window(dt: datetime, start: datetime, end: datetime) -> bool:
    return start <= dt <= end


def _pct(value: float | str | None) -> str:
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    return f"{number:g}%"


def _signed(value: float, suffix: str = "") -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:g}{suffix}"


def _event(
    *,
    event_id: str,
    dt: datetime,
    title: str,
    country: str,
    tier: str,
    tags: tuple[str, ...],
    source: str,
    source_url: str,
    provider: str,
    actual: str = "",
    forecast: str = "",
    previous: str = "",
    category: str = "總體經濟",
    importance: int = 3,
    expects_result: bool = True,
) -> core.MarketEvent:
    return core.MarketEvent(
        event_id=event_id,
        time_tpe=dt,
        title=title,
        category=category,
        importance=importance,
        tier=tier,
        country=country,
        market_tags=tags,
        actual=actual,
        forecast=forecast,
        previous=previous,
        source=source,
        source_url=source_url,
        status="released" if actual else "scheduled",
        expects_result=expects_result,
        provider=provider,
    )


def _parse_ics_datetime(line: str) -> datetime | None:
    value = line.split(":", 1)[-1].strip()
    if not value:
        return None
    tz = NY
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d"):
        try:
            parsed = datetime.strptime(value.rstrip("Z"), fmt)
            if fmt == "%Y%m%d":
                parsed = parsed.replace(hour=8, minute=30)
            if value.endswith("Z"):
                return parsed.replace(tzinfo=ZoneInfo("UTC")).astimezone(TPE)
            return parsed.replace(tzinfo=tz).astimezone(TPE)
        except ValueError:
            continue
    return None


def _unfold_ics(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _bls_observations(series_ids: list[str], now: datetime, refresh_token: str) -> dict[str, list[tuple[date, float]]]:
    payload = {"seriesid": series_ids, "startyear": str(max(now.year - 2, 2024)), "endyear": str(now.year)}
    raw = _post_json(BLS_API_URL, payload, refresh_token)
    results: dict[str, list[tuple[date, float]]] = {}
    for series in raw.get("Results", {}).get("series", []) if isinstance(raw, dict) else []:
        sid = str(series.get("seriesID") or "")
        values: list[tuple[date, float]] = []
        for row in series.get("data", []):
            period = str(row.get("period") or "")
            if not re.fullmatch(r"M\d{2}", period):
                continue
            try:
                month = int(period[1:])
                year = int(row.get("year"))
                value = float(str(row.get("value")).replace(",", ""))
                values.append((date(year, month, 1), value))
            except (TypeError, ValueError):
                continue
        results[sid] = sorted(values)
    return results


def _bls_latest_values(family: str, now: datetime, refresh_token: str) -> tuple[str, str]:
    if family == "cpi":
        obs = _bls_observations(["CUUR0000SA0"], now, refresh_token).get("CUUR0000SA0", [])
        if len(obs) < 14:
            return "", ""
        by_month = {d: v for d, v in obs}
        months = sorted(by_month)
        latest, prev_month = months[-1], months[-2]

        def yoy(month: date) -> float | None:
            prior = date(month.year - 1, month.month, 1)
            if prior not in by_month or not by_month[prior]:
                return None
            return (by_month[month] / by_month[prior] - 1.0) * 100.0

        a, p = yoy(latest), yoy(prev_month)
        return (_pct(round(a, 1)) if a is not None else "", _pct(round(p, 1)) if p is not None else "")
    if family == "nfp":
        obs = _bls_observations(["CES0000000001"], now, refresh_token).get("CES0000000001", [])
        if len(obs) < 3:
            return "", ""
        actual = obs[-1][1] - obs[-2][1]
        previous = obs[-2][1] - obs[-3][1]
        return _signed(round(actual), "K"), _signed(round(previous), "K")
    return "", ""


def _us_bls_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    text = _fetch_text(BLS_ICS_URL, refresh_token)
    if not text:
        return [], False
    events: list[core.MarketEvent] = []
    blocks = text.split("BEGIN:VEVENT")
    now = datetime.now(TPE)
    latest_cache: dict[str, tuple[str, str]] = {}
    for block in blocks[1:]:
        lines = _unfold_ics(block)
        summary = next((line.split(":", 1)[1].strip() for line in lines if line.startswith("SUMMARY:")), "")
        dt_line = next((line for line in lines if line.startswith("DTSTART")), "")
        dt = _parse_ics_datetime(dt_line)
        if dt is None or not _in_window(dt, start, end):
            continue
        lower = summary.lower()
        if "consumer price index" in lower:
            family, title, tier = "cpi", "美國消費者物價指數（CPI）", "S"
            tags = ("美國", "通膨", "Fed", "NASDAQ", "台指")
        elif "employment situation" in lower:
            family, title, tier = "nfp", "美國非農就業人數（NFP）", "S"
            tags = ("美國", "就業", "Fed", "美元", "NASDAQ")
        else:
            continue
        actual = previous = ""
        if now >= dt + timedelta(minutes=5):
            if family not in latest_cache:
                latest_cache[family] = _bls_latest_values(family, now, refresh_token)
            actual, previous = latest_cache[family]
        events.append(
            _event(
                event_id=f"official-us-bls-{family}-{dt:%Y%m%d}", dt=dt, title=title, country="美國", tier=tier,
                tags=tags, source="U.S. Bureau of Labor Statistics (BLS)", source_url=BLS_ICS_URL,
                provider=f"official-us-bls-{family}", actual=actual, previous=previous,
            )
        )
    return events, True


def _parse_us_month_day(text: str, year: int) -> date | None:
    cleaned = re.sub(r"\s+", " ", text.strip())
    m = re.search(r"([A-Z][a-z]+)\s+(\d{1,2})", cleaned)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)} {year}", "%B %d %Y").date()
    except ValueError:
        return None


def _us_bea_schedule(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    html = _fetch_text(BEA_SCHEDULE_URL, refresh_token)
    if not html:
        return [], False
    rows = _table_rows(html)
    events: list[core.MarketEvent] = []
    now = datetime.now(TPE)
    for row in rows:
        if len(row) < 2:
            continue
        joined = " | ".join(row)
        date_match = re.search(r"([A-Z][a-z]+\s+\d{1,2})\s+(\d{1,2}:\d{2})\s*(AM|PM)", joined)
        if not date_match:
            continue
        day = _parse_us_month_day(date_match.group(1), now.year)
        if day is None:
            continue
        try:
            local_time = datetime.strptime(f"{date_match.group(2)} {date_match.group(3)}", "%I:%M %p").time()
        except ValueError:
            continue
        dt = datetime.combine(day, local_time, tzinfo=NY).astimezone(TPE)
        if not _in_window(dt, start, end):
            continue
        title_raw = row[-1]
        lower = title_raw.lower()
        if "personal income and outlays" in lower:
            family, title, tier = "pce", "美國個人消費支出物價指數（PCE）", "S"
            tags = ("美國", "PCE", "Fed", "利率", "NASDAQ")
        elif "gdp" in lower and any(k in lower for k in ("estimate", "quarter")):
            family = "gdp"
            title = f"美國國內生產毛額（GDP）－{title_raw.replace('GDP ', '').strip()}"
            tier = "A"
            tags = ("美國", "GDP", "景氣", "利率", "美股")
        else:
            continue
        actual = previous = ""
        if now >= dt + timedelta(minutes=5):
            actual, previous = _bea_latest_result(family, refresh_token)
        events.append(
            _event(
                event_id=f"official-us-bea-{family}-{dt:%Y%m%d}", dt=dt, title=title, country="美國", tier=tier,
                tags=tags, source="U.S. Bureau of Economic Analysis (BEA)", source_url=BEA_SCHEDULE_URL,
                provider=f"official-us-bea-{family}", actual=actual, previous=previous,
            )
        )
    return events, True


def _bea_latest_result(family: str, refresh_token: str) -> tuple[str, str]:
    listing = _fetch_text(BEA_RELEASES_URL, refresh_token)
    if not listing:
        return "", ""
    href = ""
    for text, url in _links(listing, BEA_RELEASES_URL):
        lower = text.lower()
        if family == "gdp" and "gdp" in lower and "estimate" in lower:
            href = url
            break
        if family == "pce" and "personal income and outlays" in lower:
            href = url
            break
    if not href:
        return "", ""
    text = _plain_text(_fetch_text(href, refresh_token))
    if family == "gdp":
        m = re.search(r"real gross domestic product \(gdp\) (?:increased|decreased) at an annual rate of\s+(-?\d+(?:\.\d+)?)\s+percent", text, re.I)
        if not m:
            m = re.search(r"real GDP (?:increased|decreased).*?(-?\d+(?:\.\d+)?)\s+percent", text, re.I)
        return (_pct(m.group(1)) if m else "", "")
    m = re.search(r"from the same month one year ago, the PCE price index (?:increased|decreased)\s+(-?\d+(?:\.\d+)?)\s+percent", text, re.I)
    if not m:
        m = re.search(r"PCE price index.*?from the same month one year ago.*?(-?\d+(?:\.\d+)?)\s+percent", text, re.I)
    return (_pct(m.group(1)) if m else "", "")


def _month_number(name: str) -> int | None:
    names = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
        "nov": 11, "november": 11, "dec": 12, "december": 12,
    }
    return names.get(name.strip().lower().rstrip("."))


def _us_fomc_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    text = _plain_text(_fetch_text(FED_FOMC_URL, refresh_token))
    if not text:
        return [], False
    events: list[core.MarketEvent] = []
    for year in sorted({start.year, end.year}):
        section_m = re.search(rf"\b{year}\s+FOMC Meetings\b(.*?)(?=\b{year + 1}\s+FOMC Meetings\b|$)", text, re.I)
        section = section_m.group(1) if section_m else text
        for m in re.finditer(r"\b(January|March|April|May|June|July|September|October|November|December)\s+(\d{1,2})(?:-(\d{1,2}))?\*?", section, re.I):
            month = _month_number(m.group(1))
            day = int(m.group(3) or m.group(2))
            if month is None:
                continue
            try:
                meeting_day = date(year, month, day)
            except ValueError:
                continue
            dt = _dt_local(meeting_day, 14, 0, NY)
            if not _in_window(dt, start, end):
                continue
            actual, previous = _fed_target_result(meeting_day, refresh_token) if datetime.now(TPE) >= dt + timedelta(minutes=5) else ("", "")
            events.append(
                _event(
                    event_id=f"official-us-fed-fomc-{meeting_day.isoformat()}", dt=dt,
                    title="美國聯邦公開市場委員會（FOMC）利率決議", country="美國", tier="S",
                    tags=("美國", "FOMC", "Fed", "利率", "全球風險資產"), source="Federal Reserve",
                    source_url=FED_FOMC_URL, provider="official-us-fed-fomc", actual=actual, previous=previous,
                    category="央行事件",
                )
            )
    return core._dedupe(events), True


def _fed_target_result(meeting_day: date, refresh_token: str) -> tuple[str, str]:
    url = f"{FED_PRESS_BASE}{meeting_day:%Y%m%d}a.htm"
    text = _plain_text(_fetch_text(url, refresh_token))
    m = re.search(r"target range for the federal funds rate (?:at|to)\s+([\d.]+)\s+to\s+([\d.]+)\s+percent", text, re.I)
    if not m:
        return "", ""
    return f"{m.group(1)}–{m.group(2)}%", ""


def _roc_year_to_ad(value: int) -> int:
    return value + 1911 if value < 1911 else value


def _tw_schedule_from_row(row: list[str], family: str, now: datetime) -> list[core.MarketEvent]:
    if family == "cpi":
        if not any("消費者物價指數" in cell for cell in row):
            return []
        title, tier, tags = "台灣消費者物價指數（CPI）", "S", ("台灣", "CPI", "通膨", "台股", "央行")
    else:
        if not any(("國民所得" in cell or "國內生產毛額" in cell) for cell in row):
            return []
        title, tier, tags = "台灣國內生產毛額（GDP）", "A", ("台灣", "GDP", "景氣", "台股")
    cells = row[3:] if len(row) > 3 else row
    result: list[core.MarketEvent] = []
    for cell in cells:
        m = re.search(r"(?<!\d)(\d{1,2})\s+(\d{1,2}):(\d{2})\s*\((\d{3})(\d{2})\)", cell)
        if not m:
            continue
        release_day, hh, mm = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ref_year = _roc_year_to_ad(int(m.group(4)))
        ref_month = int(m.group(5))
        release_year, release_month = ref_year, ref_month + 1
        if release_month == 13:
            release_year += 1
            release_month = 1
        if family == "gdp" and release_month not in {2, 5, 8, 11}:
            continue
        try:
            dt = _dt_local(date(release_year, release_month, release_day), hh, mm, TPE)
        except ValueError:
            continue
        actual = previous = ""
        if datetime.now(TPE) >= dt + timedelta(minutes=5):
            actual, previous = _tw_latest_result(family, refresh_token=f"tw-{now:%Y%m%d%H%M}")
        result.append(
            _event(
                event_id=f"official-tw-dgbas-{family}-{dt:%Y%m%d}", dt=dt, title=title, country="台灣", tier=tier,
                tags=tags, source="行政院主計總處", source_url=TW_CPI_SCHEDULE_URL if family == "cpi" else TW_GDP_SCHEDULE_URL,
                provider=f"official-tw-dgbas-{family}", actual=actual, previous=previous,
            )
        )
    return result


def _tw_dgbas_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    cpi_html = _fetch_text(TW_CPI_SCHEDULE_URL, refresh_token)
    gdp_html = _fetch_text(TW_GDP_SCHEDULE_URL, refresh_token)
    events: list[core.MarketEvent] = []
    now = datetime.now(TPE)
    if cpi_html:
        for row in _table_rows(cpi_html):
            events.extend(_tw_schedule_from_row(row, "cpi", now))
    if gdp_html:
        for row in _table_rows(gdp_html):
            events.extend(_tw_schedule_from_row(row, "gdp", now))
    events = [e for e in events if _in_window(e.time_tpe, start, end)]
    return core._dedupe(events), bool(cpi_html or gdp_html)


def _tw_latest_result(family: str, refresh_token: str) -> tuple[str, str]:
    text = _plain_text(_fetch_text(TW_NEWS_URL, refresh_token))
    if family == "cpi":
        matches = re.findall(r"CPI[^。；%％]{0,80}?年增\s*([+-]?\d+(?:\.\d+)?)\s*[％%]", text, re.I)
        if not matches:
            matches = re.findall(r"消費者物價[^。；%％]{0,100}?年增\s*([+-]?\d+(?:\.\d+)?)\s*[％%]", text)
        return (_pct(matches[0]) if matches else "", _pct(matches[1]) if len(matches) > 1 else "")
    matches = re.findall(r"(?:經濟成長率|GDP[^。；%％]{0,60}?yoy)[^。；%％]{0,60}?([+-]?\d+(?:\.\d+)?)\s*[％%]", text, re.I)
    return (_pct(matches[0]) if matches else "", _pct(matches[1]) if len(matches) > 1 else "")


def _tw_cbc_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    listing = _fetch_text(CBC_MEETING_URL, refresh_token)
    if not listing:
        return [], False
    schedule_url = ""
    for text, href in _links(listing, CBC_MEETING_URL):
        if "中央銀行理監事聯席會議預定日期" in text:
            schedule_url = href
            break
    schedule_url = schedule_url or CBC_MEETING_URL
    text = _plain_text(_fetch_text(schedule_url, refresh_token))
    if not text:
        return [], False
    events: list[core.MarketEvent] = []
    for m in re.finditer(r"(?:民國)?\s*(11\d|20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text):
        year = _roc_year_to_ad(int(m.group(1)))
        try:
            day = date(year, int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        dt = _dt_local(day, 16, 30, TPE)
        if not _in_window(dt, start, end):
            continue
        actual = ""
        if datetime.now(TPE) >= dt + timedelta(minutes=5):
            home = _plain_text(_fetch_text(CBC_HOME_URL, refresh_token))
            rate = re.search(r"重貼現率[^\d]{0,40}(\d+(?:\.\d+)?)\s*%", home)
            actual = _pct(rate.group(1)) if rate else ""
        events.append(
            _event(
                event_id=f"official-tw-cbc-{day.isoformat()}", dt=dt, title="台灣中央銀行理監事會利率決議",
                country="台灣", tier="S", tags=("台灣", "央行", "利率", "台幣", "台股"), source="中央銀行",
                source_url=schedule_url, provider="official-tw-cbc", actual=actual, category="央行事件",
            )
        )
    return core._dedupe(events), True


def _parse_english_date(text: str, default_year: int) -> date | None:
    cleaned = re.sub(r"\s+", " ", text.strip().replace("Sept.", "Sep").replace("Sept", "Sep"))
    cleaned = re.sub(r"\b(Mon|Tue|Tues|Wed|Thurs|Thu|Fri|Sat|Sun)\.?\b,?", "", cleaned, flags=re.I).strip(" ,")
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%B %d", "%b %d"):
        try:
            parsed = datetime.strptime(cleaned, fmt)
            year = parsed.year if "%Y" in fmt else default_year
            return date(year, parsed.month, parsed.day)
        except ValueError:
            continue
    return None


def _jp_cpi_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    html = _fetch_text(JP_CPI_SCHEDULE_URL, refresh_token)
    if not html:
        return [], False
    events: list[core.MarketEvent] = []
    current_year = start.year
    for row in _table_rows(html):
        if len(row) < 2:
            continue
        release = row[1]
        if not re.search(r"\b(20\d{2}|January|February|March|April|May|June|July|August|September|October|November|December)\b", release, re.I):
            continue
        year_m = re.search(r"20\d{2}", release)
        if year_m:
            current_year = int(year_m.group())
        day = _parse_english_date(release, current_year)
        if day is None:
            continue
        dt = _dt_local(day, 8, 30, JST)
        if not _in_window(dt, start, end):
            continue
        actual = previous = ""
        if datetime.now(TPE) >= dt + timedelta(minutes=5):
            actual, previous = _jp_cpi_latest(refresh_token)
        events.append(
            _event(
                event_id=f"official-jp-stat-cpi-{day.isoformat()}", dt=dt, title="日本消費者物價指數（CPI）",
                country="日本", tier="S", tags=("日本", "CPI", "通膨", "BOJ", "日圓"),
                source="Statistics Bureau of Japan", source_url=JP_CPI_SCHEDULE_URL,
                provider="official-jp-stat-cpi", actual=actual, previous=previous,
            )
        )
    return core._dedupe(events), True


def _jp_cpi_latest(refresh_token: str) -> tuple[str, str]:
    text = _plain_text(_fetch_text(JP_CPI_HOME_URL, refresh_token))
    values = re.findall(r"(?:CPI|Consumer Price Index)[^%]{0,180}?([+-]?\d+(?:\.\d+)?)\s*%[^.]{0,80}?(?:over the year|year-on-year|from the previous year)", text, re.I)
    if not values:
        values = re.findall(r"([+-]?\d+(?:\.\d+)?)\s*%[^.]{0,100}?(?:over the year|year-on-year)", text, re.I)
    return (_pct(values[0]) if values else "", _pct(values[1]) if len(values) > 1 else "")


def _jp_gdp_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    html = _fetch_text(JP_GDP_SCHEDULE_URL, refresh_token)
    if not html:
        return [], False
    events: list[core.MarketEvent] = []
    for row in _table_rows(html):
        joined = " | ".join(row)
        if "Quarter" not in joined or not any(k in joined.lower() for k in ("first preliminary", "second preliminary", "advance", "estimate")):
            continue
        date_m = re.search(r"((?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+[A-Z][a-z]+\s+\d{1,2},\s+20\d{2})", joined)
        time_m = re.search(r"(\d{1,2}:\d{2})\s*(AM|PM)", joined, re.I)
        if not date_m:
            continue
        day = _parse_english_date(date_m.group(1), start.year)
        if day is None:
            continue
        if time_m:
            t = datetime.strptime(f"{time_m.group(1)} {time_m.group(2)}", "%I:%M %p").time()
            dt = datetime.combine(day, t, tzinfo=JST).astimezone(TPE)
        else:
            dt = _dt_local(day, 8, 50, JST)
        if not _in_window(dt, start, end):
            continue
        quarter_m = re.search(r"([1-4](?:st|nd|rd|th)\s+Quarter[^|]*)", joined, re.I)
        suffix = quarter_m.group(1).strip() if quarter_m else ""
        events.append(
            _event(
                event_id=f"official-jp-esri-gdp-{day.isoformat()}", dt=dt,
                title="日本國內生產毛額（GDP）" + (f"－{suffix}" if suffix else ""), country="日本", tier="A",
                tags=("日本", "GDP", "景氣", "BOJ", "日股"), source="Cabinet Office, Government of Japan (ESRI)",
                source_url=JP_GDP_SCHEDULE_URL, provider="official-jp-esri-gdp", expects_result=False,
            )
        )
    return core._dedupe(events), True


def _jp_boj_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    text = _plain_text(_fetch_text(BOJ_MPM_URL, refresh_token))
    if not text:
        return [], False
    events: list[core.MarketEvent] = []
    for year in sorted({start.year, end.year}):
        section_m = re.search(rf"\b{year}\b(.*?)(?=\b{year + 1}\b|$)", text)
        section = section_m.group(1) if section_m else text
        for m in re.finditer(r"\b(Jan|Mar|Apr|June|July|Sept|Oct|Dec)\.?(?:\s+\d{1,2}\s*\([^)]*\),)?\s*(\d{1,2})\s*\([^)]*\)", section, re.I):
            month = _month_number(m.group(1))
            if month is None:
                continue
            try:
                day = date(year, month, int(m.group(2)))
            except ValueError:
                continue
            dt = _dt_local(day, 12, 0, JST)
            if not _in_window(dt, start, end):
                continue
            events.append(
                _event(
                    event_id=f"official-jp-boj-{day.isoformat()}", dt=dt, title="日本銀行（BOJ）金融政策決定會合",
                    country="日本", tier="S", tags=("日本", "BOJ", "利率", "日圓", "全球風險資產"),
                    source="Bank of Japan", source_url=BOJ_MPM_URL, provider="official-jp-boj", category="央行事件",
                    expects_result=False,
                )
            )
    return core._dedupe(events), True


def _parse_kr_date(cell: str, year: int, month_hint: int | None = None) -> date | None:
    m = re.search(r"(?:(20\d{2})[.\-/년]\s*)?(\d{1,2})[.\-/월]\s*(\d{1,2})", cell)
    if m:
        try:
            return date(int(m.group(1) or year), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    if month_hint is not None:
        d = re.search(r"\b(\d{1,2})\b", cell)
        if d:
            try:
                return date(year, month_hint, int(d.group(1)))
            except ValueError:
                return None
    return None


def _kr_mods_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    events: list[core.MarketEvent] = []
    health = False
    months = {(start.year, start.month), (end.year, end.month)}
    for year, month in sorted(months):
        query = urlencode({"mid": "a10308010000", "year": str(year), "month": f"{month:02d}"})
        url = f"https://mods.go.kr/schedule.es?{query}"
        html = _fetch_text(url, refresh_token)
        if not html:
            continue
        health = True
        for row in _table_rows(html):
            joined = " | ".join(row)
            if not any(k in joined for k in ("소비자물가동향", "산업활동동향")):
                continue
            day = _parse_kr_date(joined, year, month)
            if day is None:
                continue
            tm = re.search(r"\b(\d{1,2}):(\d{2})\b", joined)
            hh, mm = (int(tm.group(1)), int(tm.group(2))) if tm else (8, 0)
            dt = _dt_local(day, hh, mm, KST)
            if not _in_window(dt, start, end):
                continue
            if "소비자물가동향" in joined:
                family, title, tier = "cpi", "韓國消費者物價指數（CPI）", "S"
                tags = ("韓國", "CPI", "通膨", "BOK", "韓元")
            else:
                family, title, tier = "industry", "韓國工業生產", "A"
                tags = ("韓國", "工業生產", "景氣", "半導體")
            actual = previous = ""
            if datetime.now(TPE) >= dt + timedelta(minutes=5):
                actual, previous = _kr_latest_result(family, refresh_token)
            events.append(
                _event(
                    event_id=f"official-kr-mods-{family}-{day.isoformat()}", dt=dt, title=title, country="韓國", tier=tier,
                    tags=tags, source="Ministry of Data and Statistics, Korea", source_url=url,
                    provider=f"official-kr-mods-{family}", actual=actual, previous=previous,
                )
            )
    return core._dedupe(events), health


def _kr_latest_result(family: str, refresh_token: str) -> tuple[str, str]:
    url = KR_CPI_LIST_URL if family == "cpi" else KR_INDUSTRY_LIST_URL
    listing = _fetch_text(url, refresh_token)
    if not listing:
        return "", ""
    link = ""
    for text, href in _links(listing, url):
        if family == "cpi" and "소비자물가동향" in text:
            link = href
            break
        if family == "industry" and "산업활동동향" in text:
            link = href
            break
    body = _plain_text(_fetch_text(link, refresh_token)) if link else _plain_text(listing)
    if family == "cpi":
        values = re.findall(r"전년동월대비[^%]{0,80}?([+-]?\d+(?:\.\d+)?)\s*%", body)
        return (_pct(values[0]) if values else "", _pct(values[1]) if len(values) > 1 else "")
    values = re.findall(r"전산업[^%]{0,100}?전월대비[^%]{0,60}?([+-]?\d+(?:\.\d+)?)\s*%", body)
    return (_pct(values[0]) if values else "", _pct(values[1]) if len(values) > 1 else "")


def _kr_bok_events(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], bool]:
    html = _fetch_text(BOK_POLICY_DATES_URL, refresh_token)
    text = _plain_text(html)
    if not text:
        return [], False
    events: list[core.MarketEvent] = []
    year_match = re.search(r"(20\d{2})년", text)
    default_year = int(year_match.group(1)) if year_match else start.year
    for m in re.finditer(r"(?:(20\d{2})년\s*)?(\d{1,2})월\s*(\d{1,2})일", text):
        year = int(m.group(1) or default_year)
        try:
            day = date(year, int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        dt = _dt_local(day, 10, 0, KST)
        if not _in_window(dt, start, end):
            continue
        actual = ""
        if datetime.now(TPE) >= dt + timedelta(minutes=5):
            home = _plain_text(_fetch_text(BOK_HOME_URL, refresh_token))
            m_rate = re.search(r"Base Rate[^\d]{0,40}(\d+(?:\.\d+)?)\s*%", home, re.I)
            actual = _pct(m_rate.group(1)) if m_rate else ""
        events.append(
            _event(
                event_id=f"official-kr-bok-{day.isoformat()}", dt=dt, title="韓國銀行（BOK）利率決議",
                country="韓國", tier="S", tags=("韓國", "BOK", "利率", "韓元", "韓股"),
                source="Bank of Korea (BOK)", source_url=BOK_POLICY_DATES_URL, provider="official-kr-bok",
                actual=actual, category="央行事件",
            )
        )
    return core._dedupe(events), True


def _company_events(start: datetime, end: datetime, refresh_token: str) -> list[core.MarketEvent]:
    events: list[core.MarketEvent] = []
    for profile in core.AI_COMPANIES:
        for event in core._company_events(profile, refresh_token):
            if _in_window(event.time_tpe, start, end):
                events.append(event)
    return events


def _immediate_fallbacks(start: datetime, end: datetime) -> list[core.MarketEvent]:
    events = [
        _event(
            event_id="official-fallback-bea-2026-08-26-pce", dt=datetime(2026, 8, 26, 20, 30, tzinfo=TPE),
            title="美國個人消費支出物價指數（PCE）", country="美國", tier="S",
            tags=("美國", "PCE", "Fed", "利率", "NASDAQ"), source="U.S. Bureau of Economic Analysis (BEA)",
            source_url=BEA_SCHEDULE_URL, provider="official-us-bea-pce",
        ),
        _event(
            event_id="official-fallback-bea-2026-08-26-gdp", dt=datetime(2026, 8, 26, 20, 30, tzinfo=TPE),
            title="美國第二季國內生產毛額（GDP）第二次估值", country="美國", tier="A",
            tags=("美國", "GDP", "景氣", "利率", "美股"), source="U.S. Bureau of Economic Analysis (BEA)",
            source_url=BEA_SCHEDULE_URL, provider="official-us-bea-gdp",
        ),
        _event(
            event_id="official-fallback-bok-2026-08-27", dt=datetime(2026, 8, 27, 9, 0, tzinfo=TPE),
            title="韓國銀行（BOK）利率決議", country="韓國", tier="S",
            tags=("韓國", "BOK", "利率", "韓元", "韓股"), source="Bank of Korea (BOK)",
            source_url=BOK_POLICY_DATES_URL, provider="official-kr-bok",
        ),
        core.MarketEvent(
            event_id="jh-2026-08-27-29", time_tpe=datetime(2026, 8, 27, 12, 0, tzinfo=TPE),
            title="傑克森霍爾全球央行年會（Jackson Hole）開幕", category="央行事件", importance=3,
            tier="S", country="美國", market_tags=("Fed", "利率", "美元", "全球風險資產"),
            source="Federal Reserve Bank of Kansas City",
            source_url="https://www.kansascityfed.org/research/jackson-hole-economic-symposium/",
            expects_result=False, provider="official-us-kc-fed",
        ),
    ]
    return [e for e in events if _in_window(e.time_tpe, start, end)]


def collect_official_macro(start: datetime, end: datetime, refresh_token: str) -> tuple[list[core.MarketEvent], dict[str, bool]]:
    adapters = (
        ("us_bls", _us_bls_events), ("us_bea", _us_bea_schedule), ("us_fed", _us_fomc_events),
        ("tw_dgbas", _tw_dgbas_events), ("tw_cbc", _tw_cbc_events),
        ("jp_stat", _jp_cpi_events), ("jp_esri", _jp_gdp_events), ("jp_boj", _jp_boj_events),
        ("kr_mods", _kr_mods_events), ("kr_bok", _kr_bok_events),
    )
    events: list[core.MarketEvent] = []
    health: dict[str, bool] = {}
    for name, adapter in adapters:
        try:
            rows, ok = adapter(start, end, refresh_token)
        except Exception:
            rows, ok = [], False
        events.extend(rows)
        health[name] = ok
    events.extend(_immediate_fallbacks(start, end))
    return core._dedupe(events), health


def _official_macro_ready(events: Iterable[core.MarketEvent], health: dict[str, bool]) -> bool:
    del events
    return (
        any(health.get(k) for k in ("us_bls", "us_bea", "us_fed"))
        and any(health.get(k) for k in ("tw_dgbas", "tw_cbc"))
        and any(health.get(k) for k in ("jp_stat", "jp_esri", "jp_boj"))
        and any(health.get(k) for k in ("kr_mods", "kr_bok"))
    )


def load_event_radar(days: int = 7) -> core.RadarEvents:
    now = datetime.now(TPE)
    start = now - timedelta(hours=12)
    end = now + timedelta(days=days)
    daily_token = f"official-daily-{now.date().isoformat()}"
    macro, health = collect_official_macro(start, end, daily_token)
    companies = _company_events(start, end, daily_token)
    raw = core._dedupe([*macro, *companies])
    radar = core.RadarEvents(core._homepage_events(raw, days), raw)
    radar.source_health = health
    radar.official_macro_ready = _official_macro_ready(macro, health)
    return radar


def smart_refresh_missing(events: list[core.MarketEvent], now: datetime | None = None) -> list[core.MarketEvent]:
    now = now or datetime.now(TPE)
    due = [
        e for e in events
        if e.expects_result and not e.actual and now >= e.time_tpe + timedelta(minutes=5) and now - e.time_tpe <= timedelta(hours=12)
    ]
    if not due:
        return events
    token = f"official-smart-{now:%Y%m%d-%H%M}"
    start = now - timedelta(days=1)
    end = now + timedelta(days=1)
    refreshed: list[core.MarketEvent] = []
    if any(e.provider.startswith("official-") for e in due):
        macro, _ = collect_official_macro(start, end, token)
        refreshed.extend(macro)
    symbols = {e.symbol for e in due if e.provider == "yfinance" and e.symbol}
    profiles = {p.ticker: p for p in core.AI_COMPANIES}
    for symbol in symbols:
        profile = profiles.get(symbol)
        if profile:
            refreshed.extend(core._company_events(profile, token))
    return core._dedupe([*events, *refreshed]) if refreshed else events


def clear_event_caches() -> None:
    _fetch_text.clear()
    _post_json.clear()
    try:
        core.fetch_company_earnings.clear()
    except Exception:
        pass


load_event_radar.clear = clear_event_caches
