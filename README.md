# Market Event Radar

**Free, official-source-first financial event data for developers and investors.**

Market Event Radar normalizes high-impact macroeconomic releases, central-bank decisions, and selected major-company events into one stable JSON feed. It was extracted from the event-radar engine behind the Negentropic Ataraxia investment dashboard and now runs as a standalone public project.

## Why this exists

Most economic calendars are either tied to a commercial API, scrape a third-party calendar, or mix source discovery and authority. Market Event Radar takes a different approach:

- **Official source first** for event existence, schedule, and released values whenever practical.
- **Third-party market data only as enrichment**, not the sole authority for major events.
- **Stable normalized schema** for dashboards, bots, agents, and personal tools.
- **Asia-friendly timestamps** with an explicit Taipei-time field in the public feed.
- **No paid API required for the core macro calendar.**

## Current source families

The standalone collector currently covers first-party sources from:

- United States: Federal Reserve, BLS, BEA
- Taiwan: DGBAS, Central Bank of the Republic of China (Taiwan)
- Japan: Statistics Bureau, Cabinet Office / ESRI, Bank of Japan
- South Korea: Ministry of Data and Statistics, Bank of Korea
- Major company investor-relations announcements for selected S-tier earnings events

The refresh pipeline runs in this repository. No private dashboard repository is required to publish the feed.

## Public feed

The canonical machine-readable snapshot is:

```text
https://raw.githubusercontent.com/futurenowchen/market-event-radar/main/data/latest.json
```

The snapshot contains a rolling event window and metadata describing source health and generation time.

### Event object

```json
{
  "event_id": "official-ir-nvda-2026-08-27-q2fy27",
  "time_tpe": "2026-08-27T04:20:00+08:00",
  "title": "輝達（NVIDIA）FY2027第二季財報公布",
  "category": "企業財報",
  "importance": 3,
  "tier": "S",
  "country": "",
  "market_tags": ["AI", "GPU", "半導體"],
  "actual": "",
  "forecast": "",
  "previous": "",
  "source": "NVIDIA Investor Relations",
  "source_url": "https://investor.nvidia.com/",
  "status": "scheduled",
  "expects_result": true,
  "provider": "official-company-ir",
  "symbol": "NVDA"
}
```

## Python use

The repository also exposes a small dependency-light consumer package:

```python
from market_event_radar import fetch_latest, build_risk_windows

snapshot = fetch_latest()
windows = build_risk_windows(snapshot.events)
```

This public interface is intentionally separate from the collector internals so downstream projects can depend on the feed contract without inheriting scraper implementation details.

## Tier convention

- **S** — systemically important / likely to create a major risk window
- **A** — high-impact event worth active monitoring
- **B** — contextual event that may matter when the calendar is otherwise sparse

Tiering is an opinionated normalization layer, not investment advice.

## Design principles

1. **Authority and enrichment are separate.** A company IR page can establish that earnings exist and when they occur; a market-data provider can enrich EPS estimates later.
2. **Fail closed on uncertain schedules.** The project should not invent dates merely to keep a feed populated.
3. **Published official schedules may be cached as resilience fallbacks.** Such fallbacks must be traceable to the first-party agency that published them.
4. **Consumers should depend on the schema, not scraper internals.**
5. **The feed is public data. Personal portfolio logic does not belong here.**

## Refresh model

GitHub Actions checks the feed four times per hour. A lightweight gate chooses one of three modes:

- `daily` — rebuild the rolling seven-day event window
- `smart` — refresh recently released events that are still missing actual values
- `none` — skip network work when the snapshot is current

The generated snapshot is schema-validated before it is committed.

## Roadmap

- [x] Public repository and v2 JSON contract
- [x] Standalone official-source collectors
- [x] Unattended GitHub Actions refresh
- [x] JSON validation and official-source CI probes
- [x] Reusable Python consumer package
- [ ] Add optional iCalendar (`.ics`) output
- [ ] Expand official company-IR coverage
- [ ] Split collector adapters into a cleaner plugin-style package layout

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This project aggregates public financial-event information for informational and software-development purposes. It does not provide investment advice. Official agencies and companies remain the authoritative sources for their own releases and schedules.
