[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$Mt5DataPath,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [switch]$ListCandidates
)

$ErrorActionPreference = "Stop"

function Get-Mt5DataCandidates {
    $terminalRoot = Join-Path $env:APPDATA "MetaQuotes\Terminal"
    if (-not (Test-Path $terminalRoot)) {
        return @()
    }

    Get-ChildItem -Path $terminalRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object {
            Test-Path (Join-Path $_.FullName "MQL5")
        } |
        ForEach-Object {
            $originFile = Join-Path $_.FullName "origin.txt"
            $origin = if (Test-Path $originFile) {
                (Get-Content $originFile -Raw -ErrorAction SilentlyContinue).Trim()
            } else {
                ""
            }
            [pscustomobject]@{
                DataPath = $_.FullName
                Origin   = $origin
            }
        }
}

$source = Join-Path $RepoRoot "mt5\Services\MarketEventRadarCalendarExport.mq5"
if (-not (Test-Path $source)) {
    throw "Cannot find MQL5 Service source: $source"
}

$candidates = @(Get-Mt5DataCandidates)

if ($ListCandidates) {
    if ($candidates.Count -eq 0) {
        Write-Host "No MetaTrader 5 data directories found under $env:APPDATA\MetaQuotes\Terminal"
        exit 1
    }
    $candidates | Format-Table -AutoSize
    exit 0
}

if ($Mt5DataPath) {
    $selected = Resolve-Path $Mt5DataPath -ErrorAction Stop
    $dataPath = $selected.Path
} elseif ($candidates.Count -eq 1) {
    $dataPath = $candidates[0].DataPath
} elseif ($candidates.Count -gt 1) {
    Write-Host "Multiple MT5 data directories were found. Re-run with -Mt5DataPath using one of these paths:"
    $candidates | Format-Table -AutoSize
    exit 2
} else {
    throw "No MT5 data directory found. Start MetaTrader 5 once, then re-run this script."
}

$mql5Root = Join-Path $dataPath "MQL5"
if (-not (Test-Path $mql5Root)) {
    throw "Selected path does not look like an MT5 data directory: $dataPath"
}

$servicesDir = Join-Path $mql5Root "Services"
$destination = Join-Path $servicesDir "MarketEventRadarCalendarExport.mq5"
$commonFilesRoot = Join-Path $env:ProgramData "MetaQuotes\Terminal\Common\Files"
$expectedExport = Join-Path $commonFilesRoot "MarketEventRadar\mt5_calendar_latest.json"

if ($PSCmdlet.ShouldProcess($destination, "Install MarketEventRadar MT5 Economic Calendar Service")) {
    New-Item -ItemType Directory -Path $servicesDir -Force | Out-Null
    Copy-Item -Path $source -Destination $destination -Force
}

Write-Host ""
Write-Host "MarketEventRadar MT5 canary deployment prepared."
Write-Host "MT5 data path: $dataPath"
Write-Host "Service source installed to: $destination"
Write-Host "Expected private export after Service starts: $expectedExport"
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Open MetaEditor from the same MT5 terminal."
Write-Host "2. In Navigator > Services, open MarketEventRadarCalendarExport.mq5 and compile it (F7)."
Write-Host "3. Confirm compilation reports 0 errors."
Write-Host "4. In MT5 Navigator > Services, start MarketEventRadarCalendarExport."
Write-Host "5. Wait about one minute, then confirm mt5_calendar_latest.json exists."
Write-Host "6. From this repository run:"
Write-Host "   python scripts/canary_mt5_consensus.py --export `"$expectedExport`" --snapshot data/latest.json --require-pre-release"
Write-Host ""
Write-Host "Safety boundary: this Service only reads the Economic Calendar and writes a local/common JSON file. It contains no trade/order API calls."
