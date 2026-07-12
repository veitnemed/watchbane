[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    py -m PyInstaller --noconfirm --clean watchbane.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }

    $executable = Join-Path $repoRoot "dist\Watchbane\Watchbane.exe"
    if (!(Test-Path -LiteralPath $executable)) {
        throw "Onedir build did not produce $executable."
    }

    Write-Output "Built onedir release: $executable"
}
finally {
    Pop-Location
}
