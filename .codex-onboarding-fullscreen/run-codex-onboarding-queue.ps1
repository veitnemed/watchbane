param(
    [string]$Repo = ".",
    [string]$PromptDir = "$PSScriptRoot\prompts",
    [string]$Model = "gpt-5.5",
    [string]$Reasoning = "high",
    [int]$StopAfter = 0,
    [string]$StartAt = "",
    [switch]$AllowNetwork,
    [switch]$NoCommit
)

$ErrorActionPreference = "Stop"
$RepoPath = (Resolve-Path $Repo).Path
$PromptPath = (Resolve-Path $PromptDir).Path
$Root = $PSScriptRoot
$LogDir = Join-Path $Root "logs"
$RulesFile = Join-Path $Root "RULES.md"

New-Item -ItemType Directory -Force $LogDir | Out-Null

function Run-Git {
    param([string[]]$Args)
    & git -C $RepoPath @Args
    if ($LASTEXITCODE -ne 0) { throw "git $($Args -join ' ') failed" }
}

function Save-CurrentPatch {
    param([string]$PatchFile)
    & git -C $RepoPath add -N . 2>$null
    & git -C $RepoPath diff --binary | Out-File -FilePath $PatchFile -Encoding utf8
    & git -C $RepoPath reset | Out-Null
}

function Revert-ToCommit {
    param([string]$Commit)
    & git -C $RepoPath reset --hard $Commit | Out-Null
    & git -C $RepoPath clean -fd | Out-Null
}

$excludeFile = Join-Path $RepoPath ".git\info\exclude"
if (Test-Path $excludeFile) {
    $excludeText = Get-Content $excludeFile -Raw
    foreach ($line in @(".codex-onboarding-fullscreen/", "screens/tmp_ui/", "backup_runtime_*/", "backup_before_dev_reset_*/")) {
        if ($excludeText -notmatch [regex]::Escape($line)) { Add-Content $excludeFile "`n$line" }
    }
}

$status = @(& git -C $RepoPath status --porcelain)
if ($status.Count -ne 0) { throw "Working tree is not clean. Commit/stash/reset before starting." }

$baseTag = @(& git -C $RepoPath tag --list "before-fullscreen-onboarding")
if ($baseTag.Count -eq 0) { Run-Git @("tag", "before-fullscreen-onboarding") }

$prompts = Get-ChildItem $PromptPath -Filter "*.md" | Sort-Object Name
if ($StartAt -ne "") { $prompts = $prompts | Where-Object { $_.Name -ge $StartAt } }
if ($StopAfter -gt 0) { $prompts = $prompts | Select-Object -First $StopAfter }

foreach ($prompt in $prompts) {
    $before = (& git -C $RepoPath rev-parse HEAD).Trim()
    $name = $prompt.BaseName
    $combined = Join-Path $LogDir "$name.combined.md"
    $finalLog = Join-Path $LogDir "$name.final.md"
    $codexLog = Join-Path $LogDir "$name.codex.log"
    $patchFile = Join-Path $LogDir "$name.failed.patch"

    @("# Rules", "", (Get-Content $RulesFile -Raw), "", "# Prompt", "", (Get-Content $prompt.FullName -Raw)) |
        Out-File -FilePath $combined -Encoding utf8

    $codexArgs = @(
        "exec", "-C", $RepoPath,
        "--sandbox", "workspace-write",
        "--ask-for-approval", "never",
        "--model", $Model,
        "--config", "model_reasoning_effort=`"$Reasoning`"",
        "--output-last-message", $finalLog,
        "-"
    )

    if ($AllowNetwork) {
        $codexArgs = @(
            "exec", "-C", $RepoPath,
            "--sandbox", "workspace-write",
            "--ask-for-approval", "never",
            "--model", $Model,
            "--config", "model_reasoning_effort=`"$Reasoning`"",
            "--config", "sandbox_workspace_write.network_access=true",
            "--output-last-message", $finalLog,
            "-"
        )
    }

    Get-Content $combined -Raw | & codex @codexArgs 2>&1 | Tee-Object $codexLog

    if ($LASTEXITCODE -ne 0) {
        Save-CurrentPatch $patchFile
        Revert-ToCommit $before
        throw "Codex failed on $($prompt.Name). Reverted. Patch saved: $patchFile"
    }

    Push-Location $RepoPath
    try {
        py -m compileall desktop app candidates storage tests scripts 2>&1 | Tee-Object (Join-Path $LogDir "$name.compileall.log")
        $compileExit = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    if ($compileExit -ne 0) {
        Save-CurrentPatch $patchFile
        Revert-ToCommit $before
        throw "Compileall failed on $($prompt.Name). Reverted. Patch saved: $patchFile"
    }

    if (-not $NoCommit) {
        Run-Git @("add", "-A", ":(exclude).codex-onboarding-fullscreen", ":(exclude)screens/tmp_ui", ":(exclude)backup_runtime_*", ":(exclude)backup_before_dev_reset_*")
        Run-Git @("commit", "-m", "Fullscreen onboarding $name")
    }
}
