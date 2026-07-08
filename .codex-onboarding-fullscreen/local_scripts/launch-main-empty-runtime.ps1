param(
    [string]$Repo = ".",
    [string]$BackupRoot = "",
    [switch]$NoLaunch,
    [int]$AutoCloseSeconds = 0
)

$ErrorActionPreference = "Stop"
$RepoPath = (Resolve-Path $Repo).Path

function Resolve-ChildPath([string]$Root, [string]$Relative) {
    $combined = Join-Path $Root $Relative
    return [System.IO.Path]::GetFullPath($combined)
}

function Assert-UnderRoot([string]$Root, [string]$Target) {
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $targetFull = [System.IO.Path]::GetFullPath($Target)
    if (-not $targetFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe target outside repo: $targetFull"
    }
}

function Remove-IfExists([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force
        Write-Host "Removed: $Path"
    }
}

function Remove-RuntimeFile([string]$DataRoot, [string]$Relative) {
    $path = Resolve-ChildPath $DataRoot $Relative
    Assert-UnderRoot $RepoPath $path
    Remove-IfExists $path
}

if ($BackupRoot -eq "") {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $BackupRoot = Join-Path $env:TEMP "watchbane-onboarding-backups\$timestamp"
}

Write-Host "Creating runtime backup before empty dev launch..."
& powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\backup-runtime-data.ps1" -Repo $RepoPath -BackupRoot $BackupRoot

$dataRoot = Resolve-ChildPath $RepoPath "data"
$activeProfile = "main"
$activeProfilePath = Resolve-ChildPath $dataRoot "active_profile.json"
if (Test-Path -LiteralPath $activeProfilePath) {
    try {
        $activePayload = Get-Content -LiteralPath $activeProfilePath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($activePayload.active_profile) {
            $activeProfile = [string]$activePayload.active_profile
        }
    } catch {
        Write-Host "Could not read active_profile.json; falling back to main profile."
        $activeProfile = "main"
    }
}

if ($activeProfile -eq "main") {
    $activeDataRoot = $dataRoot
} else {
    if ($activeProfile -match '[\\/:*?"<>|]|\.\.') {
        throw "Unsafe active profile name: $activeProfile"
    }
    $activeDataRoot = Resolve-ChildPath $dataRoot ("profiles\" + $activeProfile)
}
Assert-UnderRoot $RepoPath $activeDataRoot
New-Item -ItemType Directory -Force $activeDataRoot | Out-Null

Write-Host "Active profile: $activeProfile"
Write-Host "Emptying runtime data root: $activeDataRoot"

foreach ($name in @("watchbane.sqlite3", "watchbane.sqlite", "watchbane.db")) {
    Remove-RuntimeFile $activeDataRoot $name
    Remove-RuntimeFile $activeDataRoot "$name-wal"
    Remove-RuntimeFile $activeDataRoot "$name-shm"
}

foreach ($relative in @(
    "watched\titles.json",
    "watched\meta.json",
    "candidates\pool.json",
    "candidates\criteria.json",
    "candidates\watchlist.json",
    "candidates\hidden.json",
    "cache\posters\posters.json"
)) {
    Remove-RuntimeFile $activeDataRoot $relative
}

$env:WATCHBANE_DEV_EMPTY_PROFILE = "1"
$env:WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START = "1"
$env:QT_QPA_PLATFORM = "windows"

Write-Host "Backup created: $BackupRoot"
Write-Host "Runtime is empty for this dev launch."

if ($NoLaunch) {
    Write-Host "NoLaunch set; start_app.py was not launched."
    exit 0
}

Push-Location $RepoPath
try {
    if ($AutoCloseSeconds -gt 0) {
        $process = Start-Process -FilePath "py" -ArgumentList "start_app.py" -PassThru
        Write-Host "Started start_app.py with PID $($process.Id). Auto-close in $AutoCloseSeconds seconds."
        Start-Sleep -Seconds $AutoCloseSeconds
        $process.Refresh()
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            Write-Host "Stopped start_app.py PID $($process.Id)."
        } else {
            Write-Host "start_app.py exited with code $($process.ExitCode)."
        }
    } else {
        & py start_app.py
    }
} finally {
    Pop-Location
}
