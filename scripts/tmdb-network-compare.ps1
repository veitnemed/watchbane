[CmdletBinding()]
param(
    [string]$NoVpnReport = "",
    [string]$VpnReport = "",
    [string]$OutputDirectory = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $root ".local\diagnostics" }

function Find-LatestReport {
    param([string]$Mode)
    $file = Get-ChildItem -LiteralPath $OutputDirectory -Filter "tmdb-network-$Mode-*.json" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($file) { return $file.FullName }
    return ""
}

function Read-Report {
    param([string]$Path, [string]$ExpectedMode)
    if (-not $Path) { return $null }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Report not found: $Path" }
    $report = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([int]$report.schemaVersion -ne 1) { throw "Unsupported report schema: $Path" }
    if ([string]$report.mode -ne $ExpectedMode) { throw "Expected mode '$ExpectedMode', got '$($report.mode)': $Path" }
    return $report
}

function Get-AddressClasses {
    param([object]$DnsResult)
    return @($DnsResult.addresses | ForEach-Object { [string]$_.classification })
}

function Has-PublicTrustedDns {
    param([object]$HostReport)
    foreach ($dns in @($HostReport.trustedDns)) {
        $classes = Get-AddressClasses -DnsResult $dns
        if ($classes -contains "public-ipv4" -or $classes -contains "public-ipv6") { return $true }
    }
    return $false
}

function Has-BlockedSystemDns {
    param([object]$HostReport)
    $classes = Get-AddressClasses -DnsResult $HostReport.systemDns
    return ($classes -contains "loopback" -or $classes -contains "unspecified")
}

function Get-FailureSignature {
    param([object]$Report)
    if ($null -eq $Report) { return "missing" }
    return @(
        [string]$Report.primaryFailure,
        [string]$Report.api.https.status,
        [string]$Report.api.https.error,
        [string]$Report.poster.https.status,
        [string]$Report.poster.https.error
    ) -join "|"
}

if (-not $NoVpnReport) { $NoVpnReport = Find-LatestReport -Mode "no-vpn" }
if (-not $VpnReport) { $VpnReport = Find-LatestReport -Mode "vpn" }

$direct = Read-Report -Path $NoVpnReport -ExpectedMode "no-vpn"
$vpn = Read-Report -Path $VpnReport -ExpectedMode "vpn"

$scenario = "insufficient-data"
$vpnRequired = $null
$hostsOverrideRequired = $false
$conclusion = "Run both -NoVpn and -Vpn diagnostics before comparing."

if ($null -ne $direct -and $null -eq $vpn) {
    if ($direct.networkPathAvailable -and $direct.api.https.status -eq 401) {
        $scenario = "C"
        $vpnRequired = $false
        $conclusion = "The API network path works without VPN, but TMDb rejected the token. Check the token."
    }
    elseif ($direct.networkPathAvailable -and -not $direct.posterHostAvailable) {
        $scenario = "D"
        $vpnRequired = $false
        $conclusion = "The API is reachable, but the poster host is unavailable. Diagnose image.tmdb.org separately."
    }
    elseif ((Has-BlockedSystemDns -HostReport $direct.api) -and (Has-PublicTrustedDns -HostReport $direct.api) -and $direct.networkPathAvailable) {
        $scenario = "A"
        $vpnRequired = $false
        $conclusion = "System DNS is substituted, while independent DNS has public answers and HTTPS works. Prefer DNS/DoH repair; VPN is not required."
    }
}

if ($null -ne $direct -and $null -ne $vpn) {
    $directApiPublic = (Get-AddressClasses -DnsResult $direct.api.systemDns) -match '^public-'
    if ($directApiPublic -and -not $direct.networkPathAvailable -and $vpn.networkPathAvailable) {
        $scenario = "B"
        $vpnRequired = $true
        $conclusion = "DNS is public, but TCP/TLS/HTTP works only with VPN. A VPN, proxy or another network route is required."
    }
    elseif ($direct.networkPathAvailable -and $direct.api.https.status -eq 401) {
        $scenario = "C"
        $vpnRequired = $false
        $conclusion = "The API network path works without VPN, but TMDb rejected the token. Check the token."
    }
    elseif ($direct.networkPathAvailable -and -not $direct.posterHostAvailable) {
        $scenario = "D"
        $vpnRequired = $false
        $conclusion = "The API is reachable, but the poster host is unavailable. Diagnose image.tmdb.org and poster URLs separately."
    }
    elseif ((Get-FailureSignature -Report $direct) -eq (Get-FailureSignature -Report $vpn)) {
        $scenario = "E"
        $vpnRequired = $false
        $conclusion = "VPN does not change the failure. Check firewall, proxy, antivirus, certificates, system time and token."
    }
    elseif ((Has-BlockedSystemDns -HostReport $direct.api) -and (Has-PublicTrustedDns -HostReport $direct.api) -and $direct.networkPathAvailable) {
        $scenario = "A"
        $vpnRequired = $false
        $conclusion = "System DNS is substituted, while independent DNS has public answers and HTTPS works. Prefer DNS/DoH repair; VPN is not required."
    }
    else {
        $scenario = "custom"
        $conclusion = "The reports differ, but do not match a safe automatic conclusion. Review DNS, TCP, TLS, HTTP and poster fields separately."
    }
}

$result = [ordered]@{
    schemaVersion = 1
    createdAt = (Get-Date).ToString("o")
    scenario = $scenario
    vpnRequired = $vpnRequired
    hostsOverrideRequired = $hostsOverrideRequired
    conclusion = $conclusion
    noVpnReport = if ($NoVpnReport) { [System.IO.Path]::GetFileName($NoVpnReport) } else { "" }
    vpnReport = if ($VpnReport) { [System.IO.Path]::GetFileName($VpnReport) } else { "" }
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$jsonPath = Join-Path $OutputDirectory "tmdb-network-comparison-$stamp.json"
$mdPath = Join-Path $OutputDirectory "tmdb-network-comparison-$stamp.md"
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
@(
    "# TMDb VPN comparison",
    "",
    "- Scenario: $scenario",
    "- VPN required: $(if ($null -eq $vpnRequired) { 'undetermined' } else { $vpnRequired })",
    "- Hosts override required: $hostsOverrideRequired",
    "- Conclusion: $conclusion",
    "",
    "No VPN client, DNS setting or hosts file was changed."
) | Set-Content -LiteralPath $mdPath -Encoding UTF8

Write-Output "Scenario: $scenario"
Write-Output "VPN required: $(if ($null -eq $vpnRequired) { 'undetermined' } else { $vpnRequired })"
Write-Output "Conclusion: $conclusion"
Write-Output "JSON report: $jsonPath"
Write-Output "Human report: $mdPath"

if ($scenario -eq "insufficient-data" -or $scenario -eq "custom") { exit 4 }
exit 0
