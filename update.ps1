# Poker Trainer self-update. Run by start.bat before the app starts.
#
# Checks GitHub for a newer version of the main branch and, if there is one,
# downloads it and copies it over this folder. Your progress file
# (data\progress.sqlite), the Python environment (.venv) and your token file
# are never touched, because they are not part of the download.
#
# Works without any login if the repository is public. For a private
# repository, put a GitHub fine-grained token (Contents: read-only, this
# repository only) in a file called update_token.txt next to start.bat.
#
# Any problem (offline, no access, GitHub down) prints one line and the app
# starts with the version you already have.

$ErrorActionPreference = "Stop"
$Repo = "PostModernPost/pokerguru"
$Branch = "main"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ShaFile = Join-Path $Root ".update_sha"
$TokenFile = Join-Path $Root "update_token.txt"

function Say($msg) { Write-Host "  $msg" }

try {
    # A git clone (e.g. from GitHub Desktop) updates with git when git is available.
    if ((Test-Path (Join-Path $Root ".git")) -and (Get-Command git -ErrorAction SilentlyContinue)) {
        Say "Checking for updates (git)..."
        git -C $Root pull --ff-only --quiet 2>$null
        if ($LASTEXITCODE -eq 0) { Say "Up to date." } else { Say "Couldn't pull updates; starting the version you have." }
        exit 0
    }

    $headers = @{ "User-Agent" = "poker-trainer-updater"; "Accept" = "application/vnd.github+json" }
    if (Test-Path $TokenFile) {
        $token = (Get-Content $TokenFile -Raw).Trim()
        if ($token) { $headers["Authorization"] = "Bearer $token" }
    }

    Say "Checking for updates..."
    $latest = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/commits/$Branch" -Headers $headers -TimeoutSec 20
    $sha = $latest.sha
    $have = if (Test-Path $ShaFile) { (Get-Content $ShaFile -Raw).Trim() } else { "" }
    if ($sha -eq $have) { Say "Up to date."; exit 0 }

    Say "New version found; downloading..."
    $tmp = Join-Path $env:TEMP ("pokerguru-update-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    $zip = Join-Path $tmp "update.zip"
    Invoke-WebRequest -Uri "https://api.github.com/repos/$Repo/zipball/$Branch" -Headers $headers -OutFile $zip -TimeoutSec 120
    Expand-Archive -Path $zip -DestinationPath (Join-Path $tmp "x") -Force
    $inner = Get-ChildItem (Join-Path $tmp "x") | Where-Object { $_.PSIsContainer } | Select-Object -First 1
    if (-not $inner) { throw "download had no folder inside" }

    # Replace the app folders wholesale so files removed upstream disappear too. Your own
    # files are not in these folders: .venv, data\*.sqlite, .update_sha and update_token.txt
    # all live elsewhere and are kept.
    foreach ($dir in @("trainer", "web", "scripts", "tests", "docs", "data\charts", "data\advice", "data\equity_cache")) {
        $target = Join-Path $Root $dir
        if (Test-Path $target) { Remove-Item -Path $target -Recurse -Force -ErrorAction SilentlyContinue }
    }
    Copy-Item -Path (Join-Path $inner.FullName "*") -Destination $Root -Recurse -Force
    Set-Content -Path $ShaFile -Value $sha
    Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Say ("Updated to version " + $sha.Substring(0, 7) + ".")
} catch {
    $why = $_.Exception.Message
    if ($why -match "401|403|404") {
        Say "Couldn't check for updates: GitHub refused access. If the repository is private, put a token in update_token.txt (see README)."
    } else {
        Say "Couldn't check for updates ($why). Starting the version you have."
    }
}
exit 0
