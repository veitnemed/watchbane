[CmdletBinding()]
param(
    [switch]$Status,
    [switch]$Apply,
    [switch]$Restore,
    [string]$AdapterName = "",
    [string]$BackupPath = "",
    [string]$OutputDirectory = "",
    [switch]$Yes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$actionCount = @($Status, $Apply, $Restore | Where-Object { $_ }).Count
if ($actionCount -gt 1) { throw "Use only one of -Status, -Apply or -Restore." }
if ($actionCount -eq 0) { $Status = $true }

$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $root ".local\diagnostics" }
$backupDirectory = Join-Path $OutputDirectory "dns-backups"
$recommendedDns = @("1.1.1.1", "1.0.0.1")

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-TargetAdapter {
    param([string]$RequestedName)
    if ($RequestedName) {
        $adapter = Get-NetAdapter -Name $RequestedName -ErrorAction Stop
        if ($adapter.Status -ne "Up") { throw "Adapter '$RequestedName' is not active." }
        return $adapter
    }
    $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
        Sort-Object RouteMetric, InterfaceMetric |
        Select-Object -First 1
    if ($route) {
        return Get-NetAdapter -InterfaceIndex $route.InterfaceIndex -ErrorAction Stop
    }
    $adapter = Get-NetAdapter | Where-Object { $_.Status -eq "Up" } | Sort-Object ifIndex | Select-Object -First 1
    if (-not $adapter) { throw "No active network adapter was found." }
    return $adapter
}

function Get-DnsState {
    param([object]$Adapter)
    $v4 = Get-DnsClientServerAddress -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4 -ErrorAction Stop
    $v6 = Get-DnsClientServerAddress -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv6 -ErrorAction SilentlyContinue
    return [ordered]@{
        schemaVersion = 1
        createdAt = (Get-Date).ToString("o")
        adapterName = [string]$Adapter.Name
        interfaceIndex = [int]$Adapter.ifIndex
        interfaceDescription = [string]$Adapter.InterfaceDescription
        ipv4Servers = @($v4.ServerAddresses)
        ipv6Servers = if ($v6) { @($v6.ServerAddresses) } else { @() }
    }
}

function Show-DnsState {
    param([System.Collections.IDictionary]$State)
    Write-Output "Active adapter: $($State.adapterName) (index $($State.interfaceIndex))"
    Write-Output "Description: $($State.interfaceDescription)"
    Write-Output "Current IPv4 DNS: $(if (@($State.ipv4Servers).Count) { @($State.ipv4Servers) -join ', ' } else { 'automatic/none reported' })"
    Write-Output "Current IPv6 DNS: $(if (@($State.ipv6Servers).Count) { @($State.ipv6Servers) -join ', ' } else { 'automatic/none reported' })"
    Write-Output "Proposed IPv4 DNS: $($recommendedDns -join ', ')"
}

function Confirm-ExplicitAction {
    param([string]$ExpectedText, [string]$Prompt)
    if ($Yes) { return $true }
    Write-Warning $Prompt
    $answer = Read-Host "Type '$ExpectedText' to continue"
    return $answer -ceq $ExpectedText
}

function Invoke-PostChangeChecks {
    param([string]$Label)
    & ipconfig.exe /flushdns | Out-Host
    if ($LASTEXITCODE -ne 0) { Write-Warning "ipconfig /flushdns failed with exit code $LASTEXITCODE." }
    $diagnostic = Join-Path $PSScriptRoot "tmdb-network-diagnose.ps1"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $diagnostic -NoVpn -Label $Label -OutputDirectory $OutputDirectory
    $diagnosticExit = $LASTEXITCODE
    if ($diagnosticExit -ne 0) {
        Write-Warning "Post-change TMDb diagnostics did not fully pass (exit $diagnosticExit). Use -Restore with the backup shown above if connectivity is worse."
    }
}

if ($Status) {
    $adapter = Get-TargetAdapter -RequestedName $AdapterName
    Show-DnsState -State (Get-DnsState -Adapter $adapter)
    Write-Output "Status is read-only. No DNS setting was changed."
    exit 0
}

if (-not (Test-IsAdministrator)) {
    throw "Administrator rights are required for DNS changes. Reopen PowerShell as Administrator."
}

New-Item -ItemType Directory -Force -Path $backupDirectory | Out-Null

if ($Apply) {
    $adapter = Get-TargetAdapter -RequestedName $AdapterName
    $state = Get-DnsState -Adapter $adapter
    Show-DnsState -State $state
    if (-not (Confirm-ExplicitAction -ExpectedText "CHANGE DNS" -Prompt "This will change IPv4 DNS only for '$($state.adapterName)'. A backup will be created first.")) {
        Write-Output "Cancelled. No DNS setting was changed."
        exit 5
    }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $BackupPath = Join-Path $backupDirectory "dns-$($state.interfaceIndex)-$stamp.json"
    $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $BackupPath -Encoding UTF8
    Write-Output "Backup: $BackupPath"
    Set-DnsClientServerAddress -InterfaceIndex $state.interfaceIndex -ServerAddresses $recommendedDns -ErrorAction Stop
    Write-Output "DNS changed to: $($recommendedDns -join ', ')"
    Invoke-PostChangeChecks -Label "after-dns-change"
    exit 0
}

if (-not $BackupPath) {
    $latest = Get-ChildItem -LiteralPath $backupDirectory -Filter "dns-*.json" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($latest) { $BackupPath = $latest.FullName }
}
if (-not $BackupPath -or -not (Test-Path -LiteralPath $BackupPath -PathType Leaf)) {
    throw "DNS backup was not found. Pass -BackupPath explicitly."
}
$backup = Get-Content -LiteralPath $BackupPath -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Output "Backup: $BackupPath"
Write-Output "Restore adapter: $($backup.adapterName) (index $($backup.interfaceIndex))"
Write-Output "Restore IPv4 DNS: $(if (@($backup.ipv4Servers).Count) { @($backup.ipv4Servers) -join ', ' } else { 'automatic' })"
if (-not (Confirm-ExplicitAction -ExpectedText "RESTORE DNS" -Prompt "This will restore the saved IPv4 DNS configuration.")) {
    Write-Output "Cancelled. No DNS setting was changed."
    exit 5
}
if (@($backup.ipv4Servers).Count -gt 0) {
    Set-DnsClientServerAddress -InterfaceIndex ([int]$backup.interfaceIndex) -ServerAddresses @($backup.ipv4Servers) -ErrorAction Stop
}
else {
    Set-DnsClientServerAddress -InterfaceIndex ([int]$backup.interfaceIndex) -ResetServerAddresses -ErrorAction Stop
}
Write-Output "DNS configuration restored."
Invoke-PostChangeChecks -Label "after-dns-restore"
exit 0
