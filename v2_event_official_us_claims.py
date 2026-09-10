from __future__ import annotations

import re
from datetime import date, datetime
from io import BytesIO
from urllib.request import Request, urlopen

from pypdf import PdfReader

import v2_event_official as backend
import v2_event_official_us_phase2 as phase2


CLAIMS_PDF_URL = "https://www.dol.gov/ui/data.pdf"


def _fetch_claims_pdf_text() -> str:
    req = Request(
        CLAIMS_PDF_URL,
        headers={"User-Agent": backend.USER_AGENT, "Accept": "application/pdf,*/*"},
    )
    try:
        with urlopen(req, timeout=15) as response:
            raw = response.read()
        reader = PdfReader(BytesIO(raw))
        return " ".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


def _parse_claims_pdf_text(text: str) -> tuple[date | None, dict[str, str]]:
    if not text:
        return None, {}
    normalized = " ".join(text.split())

    release = re.search(
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s+"
        r"([A-Za-z]+\s+\d{1,2},\s+20\d{2})",
        normalized,
        re.I,
    )
    release_day = phase2._parse_release_day(release.group(1)) if release else None

    actual_match = re.search(
        r"advance figure for seasonally adjusted initial claims was\s+([\d,]+)",
        normalized,
        re.I,
    )
    previous_match = re.search(
        r"previous week's level was\s+(?:revised.*?\bto|unrevised at)\s+([\d,]+)",
        normalized,
        re.I,
    )
    average_match = re.search(
        r"4-week moving average was\s+([\d,]+)",
        normalized,
        re.I,
    )

    if release_day is None or actual_match is None:
        return None, {}
    return release_day, {
        "initial_claims": phase2._fmt_claims(actual_match.group(1)),
        "previous_claims": phase2._fmt_claims(previous_match.group(1)) if previous_match else "",
        "four_week_average": phase2._fmt_claims(average_match.group(1)) if average_match else "",
    }


def _claims_metrics(event, now: datetime, refresh_token: str):
    del refresh_token
    latest_day, values = _parse_claims_pdf_text(_fetch_claims_pdf_text())
    if latest_day is None:
        return []

    event_day = event.time_tpe.astimezone(backend.NY).date()
    released = now >= event.time_tpe and latest_day == event_day
    if released:
        previous = values.get("previous_claims", "")
    elif latest_day < event_day:
        previous = values.get("initial_claims", "")
    else:
        previous = ""

    actual = values.get("initial_claims", "") if released else ""
    result = []
    if actual or previous:
        result.append(
            phase2._metric(
                "initial_claims",
                "初領失業救濟金",
                actual=actual,
                previous=previous,
                unit="K",
                is_primary=True,
                source_series="DOL UI Weekly Claims PDF",
            )
        )
    if released and values.get("four_week_average"):
        result.append(
            phase2._metric(
                "four_week_average",
                "4週移動平均",
                actual=values["four_week_average"],
                unit="K",
                source_series="DOL UI Weekly Claims PDF",
            )
        )
    return result


def install() -> None:
    phase2._claims_metrics = _claims_metrics


install()
