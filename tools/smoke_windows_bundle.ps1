[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $BundleDirectory
)

$ErrorActionPreference = "Stop"
$exe = Join-Path (Resolve-Path -LiteralPath $BundleDirectory) 'Watchbane.exe'
if (!(Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "The supplied folder does not contain Watchbane.exe."
}

$profilePath = Join-Path ([System.IO.Path]::GetTempPath()) ("watchbane-smoke-" + [Guid]::NewGuid())
$settings = @{
    WATCHBANE_DATA_DIR = $profilePath
    SERIES_LIST_GUI_EVENT_LOG = '1'
    WATCHBANE_INTERFACE_LANGUAGE = 'ru'
    WATCHBANE_DATA_LANGUAGE = 'ru'
    QT_QPA_PLATFORM = 'offscreen'
    WATCHBANE_STORY_SEED_CATALOG = $null
    WATCHBANE_STORY_MODEL_DIR = $null
    WATCHBANE_DEV_EMPTY_PROFILE = $null
    WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START = $null
    TMDB_ACCESS_TOKEN = $null
    TMDB_API_KEY = $null
    TMDB_TOKEN = $null
    # Qt and its extensions must resolve from the onedir application, not
    # an installed Python or Qt. Keep only core Windows executable lookup.
    PATH = (Join-Path $env:SystemRoot 'System32')
}
$previous = @{}
$process = $null
try {
    foreach ($entry in $settings.GetEnumerator()) {
        $previous[$entry.Key] = [Environment]::GetEnvironmentVariable($entry.Key, 'Process')
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
    }
    [void][System.IO.Directory]::CreateDirectory($profilePath)
    $process = Start-Process -FilePath $exe -WorkingDirectory $profilePath -PassThru
    $limit = (Get-Date).AddSeconds(60)
    $shown = $false
    while ((Get-Date) -lt $limit -and !$shown) {
        if ($process.HasExited) {
            throw "Watchbane.exe exited before showing a window (code $($process.ExitCode))."
        }
        $logs = Get-ChildItem -LiteralPath $profilePath -Filter '*_gui_session.jsonl' -File -Recurse -ErrorAction SilentlyContinue
        foreach ($log in $logs) {
            $shown = $shown -or (Select-String -LiteralPath $log.FullName -Pattern '"event": "app.window.shown"' -Quiet)
            if (Select-String -LiteralPath $log.FullName -Pattern '"event": "app.error"' -Quiet) {
                throw "Watchbane logged a bootstrap error in the disposable profile."
            }
        }
        if (!$shown) { Start-Sleep -Milliseconds 250 }
    }
    if (!$shown) { throw "No GUI readiness event within 60 seconds." }
    Write-Output 'Verified: frozen Windows bundle showed its Qt window with no Python on PATH.'
}
finally {
    if ($null -ne $process -and !$process.HasExited) {
        if (!$process.CloseMainWindow() -or !$process.WaitForExit(4000)) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            [void]$process.WaitForExit(5000)
        }
    }
    foreach ($entry in $previous.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
    }
    if (Test-Path -LiteralPath $profilePath) {
        Remove-Item -LiteralPath $profilePath -Recurse -Force
    }
}
