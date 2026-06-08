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

# ─── Email notification setup ─────────────────────────────────────────────────
# Headless Task Scheduler runs cannot use an interactive Claude.ai Gmail MCP, so
# this sends directly via Gmail SMTP. Requires a Gmail App Password (2FA must be
# on) in credentials\.env:  GMAIL_USER=you@gmail.com  GMAIL_APP_PASSWORD=xxxx...
# No creds -> email is silently skipped; the run is unaffected.

function Get-DotEnv($path) {
    $h = @{}
    if (Test-Path $path) {
        foreach ($line in Get-Content $path) {
            if ($line -match '^\s*#') { continue }
            if ($line -match '^\s*([^=]+?)\s*=\s*(.*)$') { $h[$Matches[1].Trim()] = $Matches[2].Trim() }
        }
    }
    return $h
}

$envVars    = Get-DotEnv (Join-Path $ROOT "credentials\.env")
$GMAIL_USER = $envVars['GMAIL_USER']
$GMAIL_PASS = if ($envVars['GMAIL_APP_PASSWORD']) { $envVars['GMAIL_APP_PASSWORD'] -replace '\s','' } else { $null }
$NOTIFY_TO  = if ($env:AE_NOTIFY_TO) { $env:AE_NOTIFY_TO } else { "vinaip@gmail.com" }
$NOTIFY_CC  = if ($env:AE_NOTIFY_CC) { $env:AE_NOTIFY_CC } else { "vinai@intellisoft.com.sg" }

function Send-CompletionEmail($subject, $body) {
    if (-not $GMAIL_USER -or -not $GMAIL_PASS) {
        Log "EMAIL skipped: set GMAIL_USER + GMAIL_APP_PASSWORD in credentials\.env to enable notifications"
        return
    }
    try {
        $sec  = ConvertTo-SecureString $GMAIL_PASS -AsPlainText -Force
        $cred = New-Object System.Management.Automation.PSCredential($GMAIL_USER, $sec)
        $params = @{
            From       = $GMAIL_USER
            To         = $NOTIFY_TO
            Subject    = $subject
            Body       = $body
            SmtpServer = "smtp.gmail.com"
            Port       = 587
            UseSsl     = $true
            Credential = $cred
            Encoding   = ([System.Text.Encoding]::UTF8)   # PS 5.1: em-dashes in ae5 summaries mangle without this
            ErrorAction = "Stop"
        }
        if ($NOTIFY_CC) { $params.Cc = $NOTIFY_CC }
        Send-MailMessage @params
        Log "EMAIL sent to $NOTIFY_TO$(if ($NOTIFY_CC) { " (cc $NOTIFY_CC)" })"
    } catch {
        Log "EMAIL failed: $_"
    }
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
$stagedRecords  = @()   # rich per-article records for the completion email

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

            if ($okLine -and (Test-Path $improvePath)) {
                $siteDigestLines += $okLine
                $stagedRecords += [pscustomobject]@{
                    site    = $site
                    slug    = $slug
                    status  = $status
                    summary = ($okLine -replace '\[ae5-ok\]\s*', '')
                }
                Log "  OK: $okLine"
            } elseif ($okLine) {
                # Signal says ok but ae5 left no staged file — don't stage/email a dead path
                Log "  WARN: $slug - [ae5-ok] signal but no _improve\04-seo.html on disk; not staged"
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

# ─── Completion email (only when something is staged) ─────────────────────────

$errCount = (Get-Content $LOG | Where-Object { $_ -match '\b(ERROR|WARN)\b' }).Count
$nStaged  = $stagedRecords.Count

if ($nStaged -gt 0) {
    # Pull title / live URL / WP edit URL per slug (grouped by site) from status yaml
    $metaBySlug = @{}
    foreach ($grp in ($stagedRecords | Group-Object site)) {
        $slugList = @($grp.Group | ForEach-Object { $_.slug })
        try {
            $json = & $PYTHON -m scripts.slug_meta $grp.Name @slugList 2>$null
            $obj  = ($json -join "`n") | ConvertFrom-Json
            foreach ($s in $slugList) { $metaBySlug["$($grp.Name)/$s"] = $obj.$s }
        } catch {
            Log "EMAIL: slug_meta lookup failed for $($grp.Name): $_"
        }
    }

    $body = New-Object System.Collections.Generic.List[string]
    $body.Add("$nStaged article(s) were optimised tonight and are STAGED for your approval.")
    $body.Add("Nothing is live yet - you decide what to apply.")
    $body.Add("")
    $body.Add("REVIEW, EDIT & APPROVE (before/after diff + buttons):")
    $body.Add("  cd $ROOT; python -m scripts.review_server   ->  http://127.0.0.1:5001")
    $body.Add("Stagings accumulate and persist - approve whenever you're next at your desk.")
    $body.Add("")
    $body.Add("Or approve from the command line (details per article below):")
    $body.Add("")

    $i = 0
    foreach ($rec in $stagedRecords) {
        $i++
        $m       = $metaBySlug["$($rec.site)/$($rec.slug)"]
        $title   = if ($m -and $m.title) { $m.title } else { $rec.slug }
        $liveUrl = if ($m) { $m.url } else { "" }
        $editUrl = if ($m) { $m.edit_url } else { "" }
        $sched   = if ($m) { $m.scheduled_date } else { "" }
        $improve = "content\$($rec.site)\$($rec.slug)\_improve\04-seo.html"

        $body.Add("======================================================================")
        $body.Add("$i. $title")
        $statusLine = "   slug: $($rec.slug)   |   status: $($rec.status)"
        if ($rec.status -eq "scheduled" -and $sched) { $statusLine += " (auto-publishes $sched)" }
        $body.Add($statusLine)
        $body.Add("")
        $body.Add("   WHAT CHANGED:")
        $body.Add("     $($rec.summary)")
        $body.Add("")
        if ($liveUrl) { $body.Add("   VIEW BEFORE (current live page): $liveUrl") }
        if ($editUrl) { $body.Add("   EDIT IN WORDPRESS:               $editUrl") }
        $body.Add("   IMPROVED DRAFT (the 'after'):    $improve")
        $body.Add("")
        $body.Add("   TO APPROVE & APPLY - in PowerShell:")
        $body.Add("     cd $ROOT")
        $body.Add("     python -m scripts.apply_improvement $($rec.site) $($rec.slug)")
        if ($rec.status -eq "published") {
            $body.Add("   -> copies the improved draft and RE-PUBLISHES it live immediately.")
            if ($liveUrl) { $body.Add("      Then refresh $liveUrl to confirm.") }
        } else {
            $body.Add("   -> updates the draft only; it auto-publishes on its scheduled date.")
            $body.Add("      Nothing goes live before then. To publish sooner, edit in WordPress (link above).")
        }
        $body.Add("")
        $body.Add("   TO DISCARD this change instead:")
        $body.Add("     Remove-Item -Recurse content\$($rec.site)\$($rec.slug)\_improve")
        $body.Add("")
    }

    $body.Add("======================================================================")
    $body.Add("Apply several at once:")
    $body.Add("  cd $ROOT")
    foreach ($grp in ($stagedRecords | Group-Object site)) {
        $sl = ($grp.Group | ForEach-Object { $_.slug }) -join ' '
        $body.Add("  python -m scripts.apply_improvement $($grp.Name) $sl")
    }
    $body.Add("")
    $body.Add("Full semantic digest: status\review-$DATE.md")
    $body.Add("Run log:              logs\nightly-$DATE.log")
    if ($errCount -gt 0) { $body.Add("NOTE: $errCount warning/error line(s) in tonight's log - worth a look.") }

    $subject = "AE Nightly ${DATE}: $nStaged article(s) optimised - approval needed"
    Send-CompletionEmail $subject ($body -join "`n")
} else {
    Log "No articles staged - completion email skipped (only sends when something is staged)"
}

Log "=== nightly_improve done ==="
