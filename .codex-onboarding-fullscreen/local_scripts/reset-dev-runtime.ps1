param(
    [string]$Repo = ".",
    [switch]$ClearCandidates,
    [switch]$EmptyDatabase
)

$ErrorActionPreference = "Stop"
$RepoPath = (Resolve-Path $Repo).Path

Write-Host "DEV reset. Backup will be created first."
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = Join-Path $RepoPath "backup_before_dev_reset_$timestamp"
& powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\backup-runtime-data.ps1" -Repo $RepoPath -BackupRoot $backup

if ($EmptyDatabase) {
    foreach ($rel in @("data\watchbane.sqlite3", "data\watchbane.sqlite", "data\watchbane.db")) {
        $path = Join-Path $RepoPath $rel
        if (Test-Path $path) {
            Remove-Item $path -Force
            Write-Host "Removed dev DB: $rel"
        }
        foreach ($suffix in @("-wal", "-shm")) {
            $side = "$path$suffix"
            if (Test-Path $side) {
                Remove-Item $side -Force
                Write-Host "Removed sidecar: $rel$suffix"
            }
        }
    }
}

if ($ClearCandidates) {
    $env:WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START = "1"
    Write-Host "Set WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START=1 for this process."
}

Write-Host "Backup before reset: $backup"
