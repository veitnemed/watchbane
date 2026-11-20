[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $BundleDirectory,
    [string] $ModelDirectory,
    [switch] $SearchOnly
)

$ErrorActionPreference = "Stop"
$bundle = (Resolve-Path -LiteralPath $BundleDirectory).Path
$exe = Join-Path $bundle 'Watchbane.exe'
if (!(Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "The supplied folder does not contain Watchbane.exe."
}
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("watchbane-e5-install-" + [Guid]::NewGuid())
$model = if ($ModelDirectory) { [System.IO.Path]::GetFullPath($ModelDirectory) } else { Join-Path $temp 'local-model' }
if ($SearchOnly -and (!$ModelDirectory -or !(Test-Path -LiteralPath $model -PathType Container))) {
    throw "Search-only QA requires the model folder produced by the install acceptance step."
}
if (!$SearchOnly -and $ModelDirectory -and (Test-Path -LiteralPath $model)) {
    throw "The QA model destination must be new. The caller cleans it after all acceptance steps."
}
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
    if (!$SearchOnly) {
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
        return
    }

    # QA-only facts about four real silent films, independently phrased here.
    # This temporary file is not a shipped catalog, and uses no TMDb content.
    $cases = Join-Path $temp 'story-cases.json'
    @'
{
  "films": [
    {"key":"moon","title":"Путешествие на Луну","year":1902,"overview":"Астрономы садятся в снаряд огромной пушки и летят на Луну. Там путешественники встречают селенитов и возвращаются на Землю."},
    {"key":"gold","title":"Золотая лихорадка","year":1925,"overview":"Одинокий золотоискатель оказывается в заснеженных горах. Из-за голода он варит свой башмак и ест его со шнурками."},
    {"key":"general","title":"Генерал","year":1926,"overview":"Машинист во время Гражданской войны преследует угнанный противником паровоз, на котором оказалась его возлюбленная."},
    {"key":"caligari","title":"Кабинет доктора Калигари","year":1920,"overview":"На ярмарке доктор показывает спящего человека, который предсказывает смерть. В городе происходят убийства, и подозрение падает на сомнамбулу."}
  ],
  "queries": [
    {"text":"Учёные отправляются в космос внутри снаряда и сталкиваются с обитателями спутника Земли.","top1":"moon"},
    {"text":"Проголодавшийся старатель готовит себе ужин из собственной обуви.","top1":"gold"},
    {"text":"Железнодорожник гонится за поездом, который похитили солдаты.","top1":"general"},
    {"text":"Бродячий доктор демонстрирует на ярмарке таинственного лунатика, предрекающего гибель.","top1":"caligari"}
  ],
  "out_of_scope": "Как сварить гречку?"
}
'@ | Set-Content -LiteralPath $cases -Encoding utf8
    $searchReport = Join-Path $temp 'story-search-check.json'
    $searchArgs = @('--check-story-search', ('"{0}"' -f $model), ('"{0}"' -f $cases), ('"{0}"' -f $searchReport))
    $process = Start-Process -FilePath $exe -ArgumentList $searchArgs -WorkingDirectory $temp -PassThru
    if (!$process.WaitForExit(120000)) { throw "Frozen production story search timed out." }
    if (!(Test-Path -LiteralPath $searchReport -PathType Leaf)) {
        throw "Frozen production story search did not produce a report (exit $($process.ExitCode))."
    }
    $search = Get-Content -LiteralPath $searchReport -Raw | ConvertFrom-Json
    if ($process.ExitCode -ne 0 -or $search.status -cne 'ok' -or $search.backend -cne 'semantic_f32' -or
        $search.search_tested -cne $true -or $search.corpus_size -ne 4 -or $search.positive_total -ne 4 -or
        $search.top1_correct -ne 4 -or $search.instruction_rejected -cne $true -or
        $search.gui_tested -cne $false -or $search.collection_tested -cne $false) {
        $status = if ($search.status -is [string] -and $search.status -cin @(
            'invalid_cases', 'engine_or_query_failed', 'expectation_failed'
        )) { $search.status } else { 'invalid_report' }
        $ranks = 'unavailable'
        if ($search.expected_ranks -is [array] -and $search.expected_ranks.Count -eq 4) {
            $ranks = (@(foreach ($rank in $search.expected_ranks) {
                if (($rank -is [int] -or $rank -is [long]) -and $rank -ge 1 -and $rank -le 4) {
                    $rank
                } else { 'unranked' }
            }) -join ',')
        }
        throw "Frozen production story search failed (exit $($process.ExitCode), status $status, expected ranks $ranks)."
    }
    Write-Output 'Verified the frozen production semantic service: 4/4 authored plot paraphrases top-1 on 4 QA films and 1 rejected instructional query. Not a relevance benchmark, GUI test, or collection test.'
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
