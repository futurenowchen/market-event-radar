from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st
import yfinance as yf

TPE = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class MarketEvent:
    event_id: str
    time_tpe: datetime
    title: str
    category: str
    importance: int
    tier: str = "B"
    country: str = ""
    market_tags: tuple[str, ...] = ()
    actual: str = ""
    forecast: str = ""
    previous: str = ""
    source: str = ""
    source_url: str = ""
    status: str = "scheduled"
    expects_result: bool = False
    provider: str = "manual"
    symbol: str = ""

    def to_record(self) -> dict:
        row = asdict(self)
        row["time_tpe"] = self.time_tpe
        row["market_tags"] = " / ".join(self.market_tags)
        return row


@dataclass(frozen=True)
class CompanyProfile:
    ticker: str
    name_zh: str
    tier: str
    group: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class RiskWindow:
    time_tpe: datetime
    title: str
    tier: str
    importance: int
    events: tuple[MarketEvent, ...]


class RadarEvents(list):
    """Homepage-friendly list that still carries the complete raw event set."""

    def __init__(self, homepage_events: Iterable[MarketEvent], raw_events: Iterable[MarketEvent]):
        super().__init__(homepage_events)
        self.raw_events = list(raw_events)


MACRO_COUNTRIES = {
    "united states": "美國",
    "taiwan": "台灣",
    "japan": "日本",
    "south korea": "韓國",
}

# Broad collection universe. The homepage is deliberately narrower through S/A/B tiers.
AI_COMPANIES: tuple[CompanyProfile, ...] = (
    CompanyProfile("NVDA", "輝達（NVIDIA）", "S", "AI晶片", ("AI", "GPU", "半導體", "台積電", "NASDAQ")),
    CompanyProfile("AMD", "超微（AMD）", "S", "AI晶片", ("AI", "GPU", "CPU", "半導體", "台積電")),
    CompanyProfile("AVGO", "博通（Broadcom）", "S", "AI晶片", ("AI", "ASIC", "網路", "半導體", "台積電")),
    CompanyProfile("TSM", "台積電（TSMC）", "S", "晶圓代工", ("AI", "晶圓代工", "半導體", "台股")),
    CompanyProfile("ASML", "艾司摩爾（ASML）", "S", "半導體設備", ("AI", "EUV", "半導體設備", "台積電")),
    CompanyProfile("MSFT", "微軟（Microsoft）", "S", "雲端與AI平台", ("AI", "Azure", "雲端", "企業AI")),
    CompanyProfile("GOOGL", "Alphabet（Google）", "S", "雲端與AI平台", ("AI", "Gemini", "Google Cloud", "ASIC")),
    CompanyProfile("AMZN", "亞馬遜（Amazon）", "S", "雲端與AI平台", ("AI", "AWS", "雲端", "ASIC")),
    CompanyProfile("META", "Meta", "S", "AI平台", ("AI", "Llama", "廣告", "資本支出")),
    CompanyProfile("MU", "美光（Micron）", "A", "記憶體", ("AI", "HBM", "DRAM", "半導體")),
    CompanyProfile("000660.KS", "SK海力士（SK hynix）", "A", "記憶體", ("AI", "HBM", "DRAM", "韓國")),
    CompanyProfile("005930.KS", "三星電子（Samsung Electronics）", "A", "記憶體與晶圓", ("AI", "HBM", "DRAM", "晶圓代工", "韓國")),
    CompanyProfile("ORCL", "甲骨文（Oracle）", "A", "雲端與AI平台", ("AI", "OCI", "雲端", "資料中心")),
    CompanyProfile("ARM", "安謀（Arm）", "A", "CPU架構", ("AI", "CPU", "資料中心", "邊緣AI")),
    CompanyProfile("MRVL", "邁威爾（Marvell）", "A", "AI晶片與網路", ("AI", "ASIC", "網路", "資料中心")),
    CompanyProfile("ANET", "Arista Networks", "A", "資料中心網路", ("AI", "網路", "資料中心", "雲端")),
    CompanyProfile("CRWV", "CoreWeave", "A", "AI雲端", ("AI", "GPU雲端", "資料中心")),
    CompanyProfile("VRT", "Vertiv", "A", "資料中心電力與散熱", ("AI", "電力", "散熱", "資料中心")),
    CompanyProfile("QCOM", "高通（Qualcomm）", "A", "邊緣AI晶片", ("AI", "手機", "邊緣AI", "半導體")),
    CompanyProfile("PLTR", "帕蘭泰爾（Palantir）", "A", "AI軟體", ("AI", "企業軟體", "政府", "商業化")),
    CompanyProfile("AAPL", "蘋果（Apple）", "A", "終端AI", ("AI", "裝置端AI", "消費電子", "台灣供應鏈")),
    CompanyProfile("TSLA", "特斯拉（Tesla）", "A", "實體AI", ("AI", "自駕", "機器人", "算力")),
    CompanyProfile("INTC", "英特爾（Intel）", "B", "CPU與晶圓", ("AI", "CPU", "晶圓代工", "半導體")),
    CompanyProfile("SMCI", "美超微（Supermicro）", "B", "AI伺服器", ("AI", "伺服器", "資料中心")),
    CompanyProfile("DELL", "戴爾（Dell）", "B", "AI伺服器", ("AI", "伺服器", "企業IT")),
    CompanyProfile("HPE", "慧與科技（HPE）", "B", "AI伺服器", ("AI", "伺服器", "企業IT")),
    CompanyProfile("NOW", "ServiceNow", "B", "AI軟體", ("AI", "企業軟體", "工作流程")),
    CompanyProfile("CRM", "Salesforce", "B", "AI軟體", ("AI", "企業軟體", "CRM")),
    CompanyProfile("ADBE", "Adobe", "B", "生成式AI軟體", ("AI", "生成式AI", "創意軟體")),
    CompanyProfile("SNOW", "Snowflake", "B", "資料與AI平台", ("AI", "資料平台", "雲端")),
    CompanyProfile("IBM", "IBM", "B", "企業AI", ("AI", "企業軟體", "混合雲")),
    CompanyProfile("AMAT", "應用材料（Applied Materials）", "B", "半導體設備", ("AI", "半導體設備", "晶圓製造")),
    CompanyProfile("LRCX", "科林研發（Lam Research）", "B", "半導體設備", ("AI", "半導體設備", "記憶體")),
    CompanyProfile("KLAC", "科磊（KLA）", "B", "半導體設備", ("AI", "半導體設備", "製程控制")),
)

RELEVANT_MACRO_KEYWORDS = {
    "united states": (
        "interest rate", "fomc", "cpi", "consumer price", "pce", "personal consumption expenditures",
        "non farm", "nonfarm", "payroll", "gdp", "ism", "pmi", "retail sales", "jobless claims",
    ),
    "taiwan": (
        "interest rate", "cpi", "consumer price", "gdp", "export", "export orders", "industrial production",
    ),
    "japan": (
        "interest rate", "boj", "cpi", "consumer price", "gdp", "tankan", "wage", "industrial production", "retail sales",
    ),
    "south korea": (
        "interest rate", "bok", "cpi", "consumer price", "gdp", "export", "industrial production",
    ),
}

S_MACRO_KEYWORDS = (
    "interest rate decision", "fomc", "cpi", "consumer price", "pce", "personal consumption expenditures",
    "non farm", "nonfarm", "payroll",
)
A_MACRO_KEYWORDS = (
    "gdp", "ism", "pmi", "retail sales", "export", "tankan", "wage", "industrial production",
)
NO_RESULT_KEYWORDS = (
    "speech", "speaks", "press conference", "minutes", "meeting", "symposium", "holiday", "auction",
)

# Safety net for this first production window. Live providers remain primary.
FALLBACK_EVENTS = (
    MarketEvent(
        event_id="bea-2026-08-26-pio",
        time_tpe=datetime(2026, 8, 26, 20, 30, tzinfo=TPE),
        title="美國7月個人消費支出物價指數（PCE）",
        category="總體經濟",
        importance=3,
        tier="S",
        country="美國",
        market_tags=("Fed", "利率", "NASDAQ", "台指"),
        source="U.S. BEA",
        source_url="https://www.bea.gov/news/schedule",
        expects_result=True,
        provider="tradingeconomics",
    ),
    MarketEvent(
        event_id="bea-2026-08-26-gdp2",
        time_tpe=datetime(2026, 8, 26, 20, 30, tzinfo=TPE),
        title="美國第二季國內生產毛額（GDP）第二次估值",
        category="總體經濟",
        importance=3,
        tier="A",
        country="美國",
        market_tags=("成長", "利率", "美股", "台指"),
        source="U.S. BEA",
        source_url="https://www.bea.gov/news/schedule",
        expects_result=True,
        provider="tradingeconomics",
    ),
    MarketEvent(
        event_id="nvda-2026-08-27-q2fy27",
        time_tpe=datetime(2026, 8, 27, 4, 20, tzinfo=TPE),
        title="輝達（NVIDIA）FY2027第二季財報公布",
        category="企業財報",
        importance=3,
        tier="S",
        market_tags=("AI", "GPU", "半導體", "台積電", "台指"),
        source="NVIDIA Investor Relations",
        source_url="https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Sets-Conference-Call-for-Second-Quarter-Financial-Results/default.aspx",
        expects_result=True,
        provider="yfinance",
        symbol="NVDA",
    ),
    MarketEvent(
        event_id="jh-2026-08-27-29",
        time_tpe=datetime(2026, 8, 27, 12, 0, tzinfo=TPE),
        title="傑克森霍爾全球央行年會（Jackson Hole）開幕",
        category="央行事件",
        importance=3,
        tier="S",
        country="美國",
        market_tags=("Fed", "利率", "美元", "全球風險資產"),
        source="Federal Reserve Bank of Kansas City",
        source_url="https://www.kansascityfed.org/research/jackson-hole-economic-symposium/jackson-hole-faqs/",
        expects_result=False,
        provider="manual",
    ),
)


def _secret_value(section: str, key: str) -> str:
    try:
        block = st.secrets.get(section, {})
        if hasattr(block, "get"):
            value = block.get(key, "")
            return str(value).strip() if value else ""
    except Exception:
        pass
    return ""


def _parse_te_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    # Trading Economics calendar timestamps are commonly returned without an offset.
    # Treat those timestamps as UTC rather than discarding the event entirely.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TPE)


def _clean_number(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, float):
        return f"{value:g}"
    return str(value).strip()


def _contains(text: str, keywords: Iterable[str]) -> bool:
    lower = text.lower()
    return any(k.lower() in lower for k in keywords)


def _macro_tier(title: str, importance: int) -> str:
    if _contains(title, S_MACRO_KEYWORDS):
        return "S"
    if _contains(title, A_MACRO_KEYWORDS) or importance >= 3:
        return "A"
    return "B"


def _macro_expects_result(title: str) -> bool:
    return not _contains(title, NO_RESULT_KEYWORDS)


def _localized_macro_title(raw_title: str, country_key: str) -> str:
    country = MACRO_COUNTRIES.get(country_key, country_key)
    lower = raw_title.lower()
    suffix = ""
    if "yoy" in lower:
        suffix = "年增率"
    elif "mom" in lower:
        suffix = "月增率"
    elif "qoq" in lower:
        suffix = "季增率"

    def with_suffix(base: str) -> str:
        return f"{country}{base}" + (f"－{suffix}" if suffix else "")

    if "core pce" in lower:
        return with_suffix("核心個人消費支出物價指數（核心PCE）")
    if "pce" in lower or "personal consumption expenditures" in lower:
        return with_suffix("個人消費支出物價指數（PCE）")
    if "core cpi" in lower:
        return with_suffix("核心消費者物價指數（核心CPI）")
    if "cpi" in lower or "consumer price" in lower:
        return with_suffix("消費者物價指數（CPI）")
    if "non farm" in lower or "nonfarm" in lower or "payroll" in lower:
        return with_suffix("非農就業人數（NFP）")
    if "interest rate decision" in lower or "fomc" in lower:
        central_bank = {
            "united states": "聯邦公開市場委員會（FOMC）利率決議",
            "taiwan": "中央銀行理監事會利率決議",
            "japan": "日本銀行（BOJ）利率決議",
            "south korea": "韓國銀行（BOK）利率決議",
        }.get(country_key, "央行利率決議")
        return f"{country}{central_bank}"
    if "gdp" in lower:
        return with_suffix("國內生產毛額（GDP）")
    if "tankan" in lower:
        return "日本短觀調查（Tankan）"
    if "ism" in lower and "pmi" in lower:
        return with_suffix("ISM採購經理人指數（ISM PMI）")
    if "pmi" in lower:
        return with_suffix("採購經理人指數（PMI）")
    if "retail sales" in lower:
        return with_suffix("零售銷售")
    if "jobless claims" in lower:
        return f"{country}初領失業救濟金人數"
    if "export orders" in lower:
        return with_suffix("外銷訂單")
    if "export" in lower:
        return with_suffix("出口")
    if "industrial production" in lower:
        return with_suffix("工業生產")
    if "wage" in lower:
        return with_suffix("薪資")
    return f"{country} · {raw_title}"


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_te_country_events(country_key: str, start_date: str, end_date: str, refresh_token: str) -> list[dict]:
    del refresh_token  # cache-key only
    api_key = _secret_value("event_radar", "tradingeconomics_key")
    if not api_key:
        return []
    url = (
        f"https://api.tradingeconomics.com/calendar/country/{quote(country_key)}/"
        f"{start_date}/{end_date}?c={quote(api_key)}&f=json"
    )
    req = Request(url, headers={"User-Agent": "NA-Command-Center/2.1"})
    try:
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _normalize_te_events(rows: Iterable[dict], country_key: str) -> list[MarketEvent]:
    events: list[MarketEvent] = []
    country_zh = MACRO_COUNTRIES.get(country_key, country_key)
    relevant = RELEVANT_MACRO_KEYWORDS.get(country_key, ())
    for row in rows:
        raw_title = str(row.get("Event") or row.get("Category") or "").strip()
        if not raw_title or not _contains(raw_title, relevant):
            continue
        dt = _parse_te_datetime(row.get("Date", ""))
        if dt is None:
            continue
        importance = min(max(int(row.get("Importance") or 1), 1), 3)
        if importance < 2:
            continue
        actual = str(row.get("Actual") or "").strip()
        events.append(
            MarketEvent(
                event_id=f"te-{row.get('CalendarId', country_key + raw_title + dt.isoformat())}",
                time_tpe=dt,
                title=_localized_macro_title(raw_title, country_key),
                category="央行事件" if ("interest rate" in raw_title.lower() or "fomc" in raw_title.lower()) else "總體經濟",
                importance=importance,
                tier=_macro_tier(raw_title, importance),
                country=country_zh,
                market_tags=(country_zh, "總體經濟", "利率" if _contains(raw_title, ("rate", "cpi", "pce")) else "景氣"),
                actual=actual,
                forecast=str(row.get("Forecast") or row.get("TEForecast") or "").strip(),
                previous=str(row.get("Previous") or "").strip(),
                source=str(row.get("Source") or "Trading Economics").strip(),
                source_url=str(row.get("SourceURL") or "").strip(),
                status="released" if actual else "scheduled",
                expects_result=_macro_expects_result(raw_title),
                provider="tradingeconomics",
                symbol=str(row.get("Ticker") or row.get("Symbol") or "").strip(),
            )
        )
    return events


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_company_earnings(ticker: str, refresh_token: str) -> list[dict]:
    del refresh_token  # cache-key only
    try:
        df = yf.Ticker(ticker).get_earnings_dates(limit=8)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    records: list[dict] = []
    for idx, row in df.iterrows():
        try:
            ts = pd.Timestamp(idx)
            if ts.tzinfo is None:
                continue
            dt = ts.to_pydatetime().astimezone(TPE)
        except Exception:
            continue
        records.append(
            {
                "time_tpe": dt.isoformat(),
                "forecast": _clean_number(row.get("EPS Estimate")),
                "actual": _clean_number(row.get("Reported EPS")),
            }
        )
    return records


def _company_events(profile: CompanyProfile, refresh_token: str) -> list[MarketEvent]:
    importance = 3 if profile.tier in {"S", "A"} else 2
    events: list[MarketEvent] = []
    for row in fetch_company_earnings(profile.ticker, refresh_token):
        try:
            dt = datetime.fromisoformat(str(row.get("time_tpe", ""))).astimezone(TPE)
        except Exception:
            continue
        actual = str(row.get("actual") or "").strip()
        forecast = str(row.get("forecast") or "").strip()
        events.append(
            MarketEvent(
                event_id=f"yf-{profile.ticker}-{dt:%Y%m%d%H%M}",
                time_tpe=dt,
                title=f"{profile.name_zh}財報公布",
                category="企業財報",
                importance=importance,
                tier=profile.tier,
                market_tags=profile.tags,
                actual=f"每股盈餘（EPS） {actual}" if actual else "",
                forecast=f"每股盈餘（EPS） {forecast}" if forecast else "",
                source="Yahoo Finance / yfinance",
                status="released" if actual else "scheduled",
                expects_result=True,
                provider="yfinance",
                symbol=profile.ticker,
            )
        )
    return events


def _event_family(event: MarketEvent) -> str:
    text = f"{event.title} {event.symbol}".lower()
    families = (
        ("pce", ("pce", "個人消費支出")),
        ("cpi", ("cpi", "消費者物價")),
        ("nfp", ("nfp", "非農")),
        ("gdp", ("gdp", "國內生產毛額")),
        ("nvda", ("nvda", "nvidia", "輝達")),
    )
    for name, keys in families:
        if any(k in text for k in keys):
            return name
    return event.title.lower()


def _dedupe(events: Iterable[MarketEvent]) -> list[MarketEvent]:
    best: dict[tuple[str, str], MarketEvent] = {}
    tier_rank = {"S": 3, "A": 2, "B": 1}
    for event in events:
        key = (event.time_tpe.strftime("%Y-%m-%d %H:%M"), _event_family(event))
        current = best.get(key)
        if current is None:
            best[key] = event
            continue
        current_score = (bool(current.actual), current.provider != "manual", tier_rank.get(current.tier, 0))
        event_score = (bool(event.actual), event.provider != "manual", tier_rank.get(event.tier, 0))
        if event_score > current_score:
            best[key] = event
    return sorted(best.values(), key=lambda x: x.time_tpe)


def _smart_refresh_missing(events: list[MarketEvent], now: datetime) -> list[MarketEvent]:
    due = [
        e for e in events
        if e.expects_result
        and not e.actual
        and now >= e.time_tpe + timedelta(minutes=5)
        and now - e.time_tpe <= timedelta(hours=12)
    ]
    if not due:
        return events

    refresh_token = f"smart-{now:%Y%m%d-%H}-{(now.minute // 10) * 10:02d}"
    refreshed: list[MarketEvent] = []

    if any(e.provider == "tradingeconomics" for e in due):
        start_date = (now - timedelta(days=1)).date().isoformat()
        end_date = (now + timedelta(days=1)).date().isoformat()
        for country_key in MACRO_COUNTRIES:
            refreshed.extend(
                _normalize_te_events(
                    fetch_te_country_events(country_key, start_date, end_date, refresh_token),
                    country_key,
                )
            )

    due_symbols = {e.symbol for e in due if e.provider == "yfinance" and e.symbol}
    company_map = {p.ticker: p for p in AI_COMPANIES}
    for symbol in due_symbols:
        profile = company_map.get(symbol)
        if profile:
            refreshed.extend(_company_events(profile, refresh_token))

    return _dedupe([*events, *refreshed]) if refreshed else events


def _raw_events(events: Iterable[MarketEvent]) -> list[MarketEvent]:
    return list(getattr(events, "raw_events", events))


def build_risk_windows(events: Iterable[MarketEvent], hours: int = 36) -> list[RiskWindow]:
    now = datetime.now(TPE)
    horizon = now + timedelta(hours=hours)
    upcoming = sorted(
        [e for e in _raw_events(events) if now <= e.time_tpe <= horizon and e.tier in {"S", "A"}],
        key=lambda e: e.time_tpe,
    )
    groups: list[list[MarketEvent]] = []
    for event in upcoming:
        if not groups or event.time_tpe - groups[-1][-1].time_tpe > timedelta(minutes=10):
            groups.append([event])
        else:
            groups[-1].append(event)

    tier_rank = {"S": 3, "A": 2, "B": 1}
    windows: list[RiskWindow] = []
    for group in groups:
        if len(group) == 1:
            title = group[0].title
        elif all(e.category in {"總體經濟", "央行事件"} for e in group):
            countries = {e.country for e in group if e.country}
            prefix = next(iter(countries)) if len(countries) == 1 else "跨市場"
            title = f"{prefix}重要數據組合"
        elif all(e.category == "企業財報" for e in group):
            title = "AI產業財報集中窗口"
        else:
            title = "重要事件集中窗口"
        top_tier = max((e.tier for e in group), key=lambda t: tier_rank.get(t, 0))
        windows.append(
            RiskWindow(
                time_tpe=group[0].time_tpe,
                title=title,
                tier=top_tier,
                importance=max(e.importance for e in group),
                events=tuple(group),
            )
        )
    return windows


def _homepage_events(raw_events: list[MarketEvent], days: int) -> list[MarketEvent]:
    windows = build_risk_windows(raw_events, hours=24 * days)
    result: list[MarketEvent] = []
    covered_ids: set[str] = set()
    for idx, window in enumerate(windows):
        covered_ids.update(e.event_id for e in window.events)
        if len(window.events) == 1:
            tags = tuple(dict.fromkeys((window.tier + "級", *window.events[0].market_tags)))[:5]
        else:
            member_names = "、".join(e.title for e in window.events[:2])
            if len(window.events) > 2:
                member_names += f" 等{len(window.events)}項"
            tags = (window.tier + "級", f"{len(window.events)}項事件", member_names)
        result.append(
            MarketEvent(
                event_id=f"window-{idx}-{window.time_tpe:%Y%m%d%H%M}",
                time_tpe=window.time_tpe,
                title=window.title,
                category="風險窗口",
                importance=window.importance,
                tier=window.tier,
                market_tags=tags,
                source="金融事件雷達",
                provider="window",
            )
        )

    # If the week has very few S/A windows, allow nearby B-tier events to fill the homepage list.
    if len(result) < 3:
        now = datetime.now(TPE)
        for event in raw_events:
            if event.event_id in covered_ids or event.tier != "B" or event.time_tpe < now:
                continue
            result.append(event)
            if len(result) >= 3:
                break
    return sorted(result, key=lambda e: e.time_tpe)


def load_event_radar(days: int = 7) -> RadarEvents:
    now = datetime.now(TPE)
    end = now + timedelta(days=days)
    daily_token = f"daily-{now.date().isoformat()}"
    start_date = (now - timedelta(days=1)).date().isoformat()
    end_date = end.date().isoformat()

    events: list[MarketEvent] = []
    for country_key in MACRO_COUNTRIES:
        events.extend(
            _normalize_te_events(
                fetch_te_country_events(country_key, start_date, end_date, daily_token),
                country_key,
            )
        )
    for profile in AI_COMPANIES:
        events.extend(_company_events(profile, daily_token))
    events.extend(e for e in FALLBACK_EVENTS if now - timedelta(hours=12) <= e.time_tpe <= end)

    raw = [e for e in _dedupe(events) if now - timedelta(hours=12) <= e.time_tpe <= end]
    raw = _smart_refresh_missing(raw, now)
    return RadarEvents(_homepage_events(raw, days), raw)


def clear_event_caches() -> None:
    fetch_te_country_events.clear()
    fetch_company_earnings.clear()


# Compatibility with the existing V1/V2 hard-cache-clear hook.
load_event_radar.clear = clear_event_caches  # type: ignore[attr-defined]


def event_risk_level(events: Iterable[MarketEvent], hours: int = 36) -> tuple[str, int]:
    windows = build_risk_windows(events, hours)
    if not windows:
        return "LOW", 1
    s_windows = sum(1 for w in windows if w.tier == "S")
    if s_windows >= 2:
        return "HIGH", 3
    if s_windows >= 1 or len(windows) >= 3:
        return "ELEVATED", 2
    return "NORMAL", 1


def deterministic_context_note(events: Iterable[MarketEvent], market: dict) -> str:
    level, _ = event_risk_level(events)
    windows = build_risk_windows(events)
    tw_vix = market.get("taiwan_vix")
    rz = market.get("rz", "")
    regime = market.get("regime", "")

    pieces: list[str] = []
    if isinstance(tw_vix, (int, float)) and tw_vix >= 28:
        pieces.append("台灣VIX位於高波動區，事件更可能放大路徑而非直接提供方向")
    elif isinstance(tw_vix, (int, float)) and tw_vix >= 22:
        pieces.append("波動已升溫，事件前後宜降低對單一路徑的依賴")
    else:
        pieces.append("波動環境未顯著失控，仍以既有市場結構判讀為主")
    if rz:
        pieces.append(f"目前{rz}")
    if regime:
        pieces.append(f"盤勢標記為{regime}")
    if level in {"HIGH", "ELEVATED"}:
        pieces.append(f"未來36小時有{len(windows)}個獨立重要風險窗口")
    return "；".join(pieces) + "。"


def events_dataframe(events: Iterable[MarketEvent]) -> pd.DataFrame:
    rows = []
    now = datetime.now(TPE)
    for e in _raw_events(events):
        delta = e.time_tpe - now
        hours = delta.total_seconds() / 3600
        if hours >= 48:
            eta = f"{int(hours // 24)}天"
        elif hours >= 1:
            eta = f"{int(hours)}小時"
        elif hours >= 0:
            eta = f"{max(1, int(hours * 60))}分鐘"
        else:
            eta = "已發生"
        status = "已公布" if e.actual else "待公布" if e.expects_result else "已排定"
        rows.append(
            {
                "時間": e.time_tpe.strftime("%m/%d %H:%M"),
                "等級": e.tier,
                "事件": e.title,
                "類型": e.category,
                "倒數": eta,
                "實際值": e.actual or "—",
                "市場預期": e.forecast or "—",
                "前值": e.previous or "—",
                "資料狀態": status,
                "影響": " / ".join(e.market_tags),
                "來源": e.source or "—",
            }
        )
    return pd.DataFrame(rows)
