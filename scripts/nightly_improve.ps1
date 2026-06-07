# nightly_improve.ps1 — Phase 1 nightly triage runner (no LLM)
#
# Runs triage.py for each site and emits status/triage-<site>-<date>.md/.json.
# Scheduled via schtasks (see registration command at bottom).
# Phase 2 (LLM improvement) not wired yet — triage only.
#
# Registration (run once as admin, adjust path if needed):
#   schtasks /Create /TN "AE-NightlyImprove" /TR "powershell.exe -NonInteractive -File D:\VP\ARTICLE_ENGINE\scripts\nightly_improve.ps1" /SC DAILY /ST 06:00 /RU SYSTEM /F
#
# To verify:  schtasks /Query /TN "AE-NightlyImprove" /FO LIST
# To run now: schtasks /Run /TN "AE-NightlyImprove"
# To delete:  schtasks /Delete /TN "AE-NightlyImprove" /F

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT   # schtasks launches from system32; scripts.triage requires repo root as CWD
$LOG_DIR = Join-Path $ROOT "logs"
$PYTHON = "python"

# Create logs dir if absent
if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR | Out-Null }

$DATE = (Get-Date -Format "yyyy-MM-dd")
$LOG = Join-Path $LOG_DIR "nightly-$DATE.log"

function Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $LOG -Value $line -Encoding utf8
}

Log "=== nightly_improve start ==="

$sites = @("trainingint")

foreach ($site in $sites) {
    Log "Triaging $site..."
    try {
        $out = & $PYTHON -m scripts.triage $site 2>&1
        $out | ForEach-Object { Log "  $_" }
        Log "$site triage OK"
    } catch {
        Log "ERROR triaging ${site}: $_"
    }
}

Log "=== nightly_improve done ==="
