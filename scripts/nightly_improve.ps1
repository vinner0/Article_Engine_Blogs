# nightly_improve.ps1 — Nightly triage + LLM improvement runner
#
# Phase 1: triage.py for each site → status/triage-<site>-<date>.md/.json
# Phase 2: claude -p invoking ae-5-improve-existing for top-K articles
#           → staged _improve/ files + improve/<date> git branch + review digest
#
# Registration (run once as admin; prefer /RU with your Windows username so
# claude CLI and D:\VP paths are accessible — SYSTEM may lack both):
#   schtasks /Create /TN "AE-NightlyImprove" /TR "powershell.exe -NonInteractive -File D:\VP\ARTICLE_ENGINE\scripts\nightly_improve.ps1" /SC DAILY /ST 06:00 /RU SYSTEM /F
#
# To verify:   schtasks /Query /TN "AE-NightlyImprove" /FO LIST
# To run now:  schtasks /Run /TN "AE-NightlyImprove"
# To delete:   schtasks /Delete /TN "AE-NightlyImprove" /F
#
# Phase 2 env vars (override defaults):
#   $env:AE_TOP_K = "3"               articles per night (default 2)
#   $env:AE_SKIP_LLM = "1"            set to skip LLM pass (Phase 1 only)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT
$LOG_DIR = Join-Path $ROOT "logs"
$PYTHON = "python"
$CLAUDE = "claude"

if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR | Out-Null }

$DATE   = (Get-Date -Format "yyyy-MM-dd")
$LOG    = Join-Path $LOG_DIR "nightly-$DATE.log"
$TOP_K  = if ($env:AE_TOP_K) { [int]$env:AE_TOP_K } else { 2 }
$SKIP_LLM = ($env:AE_SKIP_LLM -eq "1")

function Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $LOG -Value $line -Encoding utf8
}

Log "=== nightly_improve start (Phase 1+2) ==="

# ─── Phase 1: triage ──────────────────────────────────────────────────────────

$sites = @("trainingint")
$triageJsonPaths = @{}

foreach ($site in $sites) {
    Log "Triaging $site..."
    try {
        $out = & $PYTHON -m scripts.triage $site 2>&1
        $out | ForEach-Object { Log "  $_" }
        $triageJsonPaths[$site] = "$ROOT\status\triage-$site-$DATE.json"
        Log "$site triage OK -> $($triageJsonPaths[$site])"
    } catch {
        Log "ERROR triaging ${site}: $_"
        $triageJsonPaths[$site] = $null
    }
}

# ─── Phase 2: LLM improvement ─────────────────────────────────────────────────

if ($SKIP_LLM) {
    Log "Phase 2 skipped (AE_SKIP_LLM=1)"
    Log "=== nightly_improve done (Phase 1 only) ==="
    exit 0
}

# Verify claude CLI is reachable
try {
    $claudeVersion = & $CLAUDE --version 2>&1
    Log "claude CLI: $claudeVersion"
} catch {
    Log "ERROR: claude CLI not found - skipping Phase 2. Add claude to PATH or set AE_SKIP_LLM=1."
    Log "=== nightly_improve done (Phase 1 only) ==="
    exit 0
}

$allDigestLines = @()

foreach ($site in $sites) {
    $jsonPath = $triageJsonPaths[$site]
    if (-not $jsonPath -or -not (Test-Path $jsonPath)) {
        Log "${site}: no triage JSON - skipping Phase 2 for this site"
        continue
    }

    $triage = Get-Content $jsonPath -Raw | ConvertFrom-Json
    $candidates = $triage.ranked | Select-Object -First $TOP_K
    Log "${site}: top-$TOP_K candidates for improvement"

    $siteDigestLines = @()

    foreach ($article in $candidates) {
        $slug    = $article.slug
        $status  = $article.status
        # Serialize findings to a compact JSON array
        $findings = ($article.findings | ConvertTo-Json -Compress)

        # Idempotency: skip if _improve/ already staged
        $improvePath = "$ROOT\content\$site\$slug\_improve\04-seo.html"
        if (Test-Path $improvePath) {
            Log "  [skip] $slug - already staged, awaiting apply"
            continue
        }

        Log "  Improving $slug (status=$status)..."
        $prompt = "Invoke the ae-5-improve-existing skill. Site: $site, Slug: $slug, Status: $status, Findings: $findings"

        try {
            $savedEAP = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            $result = & $CLAUDE --print $prompt --allowedTools "Bash,Read,Write,Edit,Glob" 2>$null
            $ErrorActionPreference = $savedEAP

            $resultText = $result -join "`n"

            # Parse signal line (last [ae5-ok] or [ae5-skip] in output); strip markdown backticks
            $okLine   = ($result | Where-Object { $_ -match '\[ae5-ok\]' }   | Select-Object -Last 1)
            $skipLine = ($result | Where-Object { $_ -match '\[ae5-skip\]' } | Select-Object -Last 1)
            if ($okLine)   { $okLine   = $okLine.Trim('`').Trim() }
            if ($skipLine) { $skipLine = $skipLine.Trim('`').Trim() }

            if ($okLine) {
                $siteDigestLines += $okLine
                Log "  OK: $okLine"
            } elseif ($skipLine) {
                Log "  SKIP: $skipLine"
            } else {
                Log "  WARN: $slug - no [ae5-ok/skip] signal from ae5"
                Log "  --- ae5 output (last 10 lines) ---"
                $result | Select-Object -Last 10 | ForEach-Object { Log "    $_" }
                Log "  --- end ae5 output ---"
            }
        } catch {
            Log "  ERROR type=$($_.GetType().Name): $slug - claude invocation failed: $_"
        }
    }

    $allDigestLines += $siteDigestLines
    Log "$site Phase 2: $($siteDigestLines.Count) article(s) staged"
}

# ─── Write review digest + commit to master (content/ is gitignored; _improve/ ────
# ─── files live on disk as staging. Only the digest lands in git.)            ────

if ($allDigestLines.Count -gt 0) {
    $digestPath = "$ROOT\status\review-$DATE.md"
    $digestLines = @(
        "# Improvement Review - $DATE",
        "",
        "Review each entry below, then apply the ones you approve:",
        "  python -m scripts.apply_improvement trainingint SLUG [SLUG...]",
        ""
    )
    $digestLines += $allDigestLines
    $digestLines += @("", "---", "_improve/ files written to content/<site>/<slug>/_improve/04-seo.html - apply or delete to clean up.")
    ($digestLines -join "`n") | Set-Content $digestPath -Encoding utf8
    Log "Wrote $digestPath"

    try {
        & git add $digestPath 2>&1 | ForEach-Object { Log "  git: $_" }
        $commitMsg = "ae5: review digest $DATE ($($allDigestLines.Count) staged)"
        & git commit -m $commitMsg 2>&1 | ForEach-Object { Log "  git: $_" }
        Log "Committed digest to master. Review: status/review-$DATE.md"
    } catch {
        Log "WARN: git commit failed - digest written but not committed: $_"
    }

    Log "Apply: python -m scripts.apply_improvement trainingint <slug> [slug...]"
} else {
    Log "No improvements staged tonight"
}

Log "=== nightly_improve done ==="
