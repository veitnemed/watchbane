[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $BundleDirectory,
    [Parameter(Mandatory = $true)] [string] $ModelDirectory
)

$ErrorActionPreference = "Stop"
$exe = Join-Path (Resolve-Path -LiteralPath $BundleDirectory).Path 'Watchbane.exe'
$model = (Resolve-Path -LiteralPath $ModelDirectory).Path
if (!(Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "The supplied folder does not contain Watchbane.exe."
}

$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("watchbane-e5-" + [Guid]::NewGuid())
$report = Join-Path $temp 'model-check.json'
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
    $args = @('--check-semantic-model', ('"{0}"' -f $model), ('"{0}"' -f $report))
    $process = Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $temp -PassThru
    if (!$process.WaitForExit(90000)) { throw "Frozen E5 check timed out." }
    if (!(Test-Path -LiteralPath $report -PathType Leaf)) {
        throw "Frozen E5 check did not produce a report (exit $($process.ExitCode))."
    }
    $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if ($process.ExitCode -ne 0 -or $result.status -cne 'ok' -or $result.variant -cne 'fp32' -or
        $result.model_tested -cne $true -or $result.search_tested -cne $false -or
        $result.embedding_size -ne 384 -or !$result.finite -or !$result.unit_norm -or !$result.differentiated) {
        throw "Frozen FP32 E5 check failed (status $($result.status), error $($result.error_type))."
    }
    Write-Output 'Verified the pinned FP32 E5 model produced distinct finite 384-dimensional embeddings inside Watchbane.exe, without Python on PATH. Search and installation were not checked by this probe.'
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
