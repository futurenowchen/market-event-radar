# Windows MT5 Canary Deployment

This runbook deploys the zero-cost MetaTrader 5 Economic Calendar canary on a Windows machine without changing the public `data/latest.json` snapshot.

## Safety model

The MQL5 Service in this repository only:

- reads MetaTrader 5 Economic Calendar data;
- filters price/jobs calendar sectors;
- writes a private/local JSON export under the MT5 common files directory.

It contains no trade/order functions and does not require a funded account.

## Prerequisites

1. Windows 10/11.
2. MetaTrader 5 installed and started at least once.
3. A working MT5 terminal connection. A demo account is sufficient for this canary.
4. This repository checked out locally.
5. Python 3.11+ if you want to run the downstream canary CLI on the same machine.

## Step 1 — prepare the Service

Open PowerShell in the repository root and run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_mt5_canary.ps1
```

If more than one MT5 data directory is detected, list candidates:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_mt5_canary.ps1 -ListCandidates
```

Then rerun with the selected data directory:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_mt5_canary.ps1 -Mt5DataPath "C:\Users\<user>\AppData\Roaming\MetaQuotes\Terminal\<terminal-id>"
```

Use `-WhatIf` to preview the copy without changing files.

## Step 2 — compile in MetaEditor

From the same MT5 terminal, open MetaEditor, locate:

`Navigator > Services > MarketEventRadarCalendarExport.mq5`

Compile with F7 and require **0 errors** before continuing.

The GitHub CI validates the Python bridge and PowerShell syntax, but cannot prove MQL5 compilation because the Ubuntu runner does not contain MetaEditor/MT5. Real-terminal compilation is therefore an explicit deployment gate.

## Step 3 — start the Service

In MT5 Navigator, under `Services`, start `MarketEventRadarCalendarExport`.

Default behavior:

- polls every 60 seconds;
- reads US / USD calendar values;
- looks back 48 hours and ahead 14 days;
- writes only price/jobs sector rows;
- writes atomically to `MarketEventRadar\mt5_calendar_latest.json` under the MT5 common files directory.

The PowerShell helper prints the expected path. On a standard Windows installation it is usually beneath:

`C:\ProgramData\MetaQuotes\Terminal\Common\Files\MarketEventRadar\mt5_calendar_latest.json`

## Step 4 — run the private canary

From the repository root:

```powershell
python scripts\canary_mt5_consensus.py `
  --export "C:\ProgramData\MetaQuotes\Terminal\Common\Files\MarketEventRadar\mt5_calendar_latest.json" `
  --snapshot data\latest.json `
  --require-pre-release
```

Expected behavior:

- provider rows are matched to official CPI / headline PPI / Initial Claims events;
- MT5 values remain labelled `provider_forecast`, not `consensus`;
- at least one matched value must have been captured before the official release when `--require-pre-release` is used;
- the command never modifies `data/latest.json`.

Optionally save a private evidence report outside the public repository:

```powershell
python scripts\canary_mt5_consensus.py `
  --export "C:\ProgramData\MetaQuotes\Terminal\Common\Files\MarketEventRadar\mt5_calendar_latest.json" `
  --snapshot data\latest.json `
  --require-pre-release `
  --output "$env:USERPROFILE\MarketEventRadarPrivate\mt5_canary_report.json"
```

## Step 5 — cross-check Myfxbook

For the same release, compare the MT5 `provider_forecast` values with Myfxbook's explicitly labelled `Consensus` values.

Do not promote MT5 to canonical survey consensus after a single match. Repeated pre-release evidence across multiple releases is required.

## Operational boundary

For the maintainer's personal deployment:

- public `market-event-radar`: official-source data + open provider logic/adapters;
- Windows MT5 node: free private provider capture;
- private overlay/dashboard: third-party forecast/consensus values and Surprise results;
- no vendor values are published into `data/latest.json` unless redistribution rights are explicit.

If the Windows machine is shut down or asleep during the pre-release capture window, no new MT5 evidence will be recorded. The official public radar remains unaffected.
