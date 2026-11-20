[CmdletBinding()]
param([string] $Python = 'python')

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    & $Python -m PyInstaller --noconfirm --clean watchbane.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }

    $bundle = Join-Path $repoRoot "dist\Watchbane"
    $required = @(
        "Watchbane.exe",
        "_internal\desktop\images\story_ticket.svg",
        "_internal\candidates\search\title_aliases.json"
    )
    foreach ($relative in $required) {
        $artifact = Join-Path $bundle $relative
        if (!(Test-Path -LiteralPath $artifact -PathType Leaf)) {
            throw "Onedir build did not produce $artifact."
        }
    }

    Write-Output "Built onedir release: $(Join-Path $bundle 'Watchbane.exe')"
}
finally {
    Pop-Location
}
