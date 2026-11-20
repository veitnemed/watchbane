[CmdletBinding()]
param([Parameter(Mandatory = $true)] [string] $BundleDirectory)

$ErrorActionPreference = "Stop"
$bundle = (Resolve-Path -LiteralPath $BundleDirectory).Path
$exe = Join-Path $bundle 'Watchbane.exe'
if (!(Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "The supplied folder does not contain Watchbane.exe."
}
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("watchbane-e5-install-" + [Guid]::NewGuid())
$model = Join-Path $temp 'local-model'
$report = Join-Path $temp 'install-check.json'
$envSettings = @{
    PATH = (Join-Path $env:SystemRoot 'System32')
    PYTHONHOME = $null
    PYTHONPATH = $null
    WATCHBANE_DATA_DIR = $temp
    WATCHBANE_STORY_MODEL_DIR = $null
    WATCHBANE_STORY_SEED_CATALOG = $null
}
$previous = @{}
$process = $null
try {
    [void][System.IO.Directory]::CreateDirectory($temp)
    foreach ($item in $envSettings.GetEnumerator()) {
        $previous[$item.Key] = [Environment]::GetEnvironmentVariable($item.Key, 'Process')
        [Environment]::SetEnvironmentVariable($item.Key, $item.Value, 'Process')
    }
    $installArgs = @('--install-semantic-model', ('"{0}"' -f $model), ('"{0}"' -f $report), '--accept-download')
    $process = Start-Process -FilePath $exe -ArgumentList $installArgs -WorkingDirectory $temp -PassThru
    if (!$process.WaitForExit(600000)) { throw "Frozen E5 installation timed out." }
    if (!(Test-Path -LiteralPath $report -PathType Leaf)) {
        throw "Frozen E5 install did not produce a report (exit $($process.ExitCode))."
    }
    $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if ($process.ExitCode -ne 0 -or $result.status -cne 'ok' -or
        $result.installation_verified -cne $true -or $result.model_tested -cne $false -or
        $result.search_tested -cne $false) {
        $status = if ($result.status -is [string] -and $result.status -ceq 'install_failed') {
            'install_failed'
        } else { 'invalid_report' }
        $stage = if ($result.failure_stage -is [string] -and $result.failure_stage -cin @('import_installer', 'install')) {
            $result.failure_stage
        } else { 'unknown' }
        $allowedCodes = @(
            'redirect_host', 'http_status', 'invalid_response', 'integrity',
            'network_or_disk', 'tls', 'timeout', 'existing_invalid', 'cancelled', 'runtime_error', 'import_error'
        )
        $code = if ($result.failure_code -is [string] -and $result.failure_code -cin $allowedCodes) {
            $result.failure_code
        } else { 'unknown' }
        throw "Frozen production E5 install failed (exit $($process.ExitCode), status $status, stage $stage, code $code)."
    }
    Write-Output 'Verified the production installer downloaded and checked the pinned E5 set inside Watchbane.exe without Python on PATH.'
    & (Join-Path $PSScriptRoot 'smoke_windows_e5.ps1') -BundleDirectory $bundle -ModelDirectory $model
}
finally {
    if ($null -ne $process -and !$process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        [void]$process.WaitForExit(5000)
    }
    foreach ($item in $previous.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($item.Key, $item.Value, 'Process')
    }
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
}
