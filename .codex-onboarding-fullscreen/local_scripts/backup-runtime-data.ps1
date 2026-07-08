param(
    [string]$Repo = ".",
    [string]$BackupRoot = ""
)

$ErrorActionPreference = "Stop"
$RepoPath = (Resolve-Path $Repo).Path

if ($BackupRoot -eq "") {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $BackupRoot = Join-Path $RepoPath "backup_runtime_$timestamp"
}

New-Item -ItemType Directory -Force $BackupRoot | Out-Null

$paths = @("data", ".env", "settings.json", "config\local_settings.json")

foreach ($rel in $paths) {
    $src = Join-Path $RepoPath $rel
    if (Test-Path $src) {
        $dst = Join-Path $BackupRoot $rel
        New-Item -ItemType Directory -Force (Split-Path $dst -Parent) | Out-Null
        Copy-Item $src $dst -Recurse -Force
        Write-Host "Backed up: $rel"
    }
}

Write-Host "Backup created: $BackupRoot"
