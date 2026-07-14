[CmdletBinding()]
param(
    [switch]$Preview,
    [switch]$Apply,
    [switch]$Remove,
    [switch]$Restore,
    [switch]$Status,
    [switch]$TryBypass,
    [string]$ApiAddress = "3.173.161.72",
    [string]$WebsiteAddress = "18.239.105.83",
    [string]$BackupPath = "",
    [string]$OutputDirectory = "",
    [int]$MaxAgeHours = 24,
    [switch]$Yes,
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$actions = @($Preview, $Apply, $Remove, $Restore, $Status | Where-Object { $_ })
if ($actions.Count -gt 1) { throw "Use only one action: -Preview, -Apply, -Remove, -Restore or -Status." }
if ($actions.Count -eq 0) { $Preview = $true }

$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $root ".local\diagnostics" }
$backupDirectory = Join-Path $OutputDirectory "hosts-backups"
$statePath = Join-Path $OutputDirectory "tmdb-hosts-state.json"
$hostsPath = Join-Path $env:SystemRoot "System32\drivers\etc\hosts"
$beginMarker = "# BEGIN WATCHBANE TEMP TMDB"
$endMarker = "# END WATCHBANE TEMP TMDB"
$requiredHosts = @(
    [ordered]@{ host = "api.themoviedb.org"; url = "https://api.themoviedb.org/3/configuration" },
    [ordered]@{ host = "image.tmdb.org"; url = "https://image.tmdb.org/t/p/w92" }
)
if ($TryBypass) {
    $requiredHosts = @(
        [ordered]@{ host = "api.themoviedb.org"; url = "https://api.themoviedb.org/3/configuration"; address = $ApiAddress },
        [ordered]@{ host = "www.themoviedb.org"; url = "https://www.themoviedb.org/"; address = $WebsiteAddress }
    )
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-PublicIPv4 {
    param([string]$Address)
    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($Address, [ref]$parsed)) { return $false }
    if ($parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $false }
    if ([System.Net.IPAddress]::IsLoopback($parsed) -or $parsed.Equals([System.Net.IPAddress]::Any)) { return $false }
    $bytes = $parsed.GetAddressBytes()
    if ($bytes[0] -eq 10) { return $false }
    if ($bytes[0] -eq 127) { return $false }
    if ($bytes[0] -eq 169 -and $bytes[1] -eq 254) { return $false }
    if ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) { return $false }
    if ($bytes[0] -eq 192 -and $bytes[1] -eq 168) { return $false }
    return $true
}

function Resolve-PublicCandidates {
    param([string]$HostName)
    try {
        return @(Resolve-DnsName -Name $HostName -Type A -Server "1.1.1.1" -DnsOnly -ErrorAction Stop |
            Where-Object { $_.Type -eq "A" -and (Test-PublicIPv4 -Address $_.IPAddress) } |
            ForEach-Object { [string]$_.IPAddress } |
            Sort-Object -Unique)
    }
    catch {
        Write-Warning "Trusted DNS lookup failed for ${HostName}: $($_.Exception.Message)"
        return @()
    }
}

function Test-DirectTcpTls {
    param([string]$HostName, [string]$Address, [int]$TimeoutMs = 7000)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($Address, 443, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
            return [ordered]@{ tcp = $false; tls = $false; error = "tcp-timeout" }
        }
        $client.EndConnect($async)
        $stream = New-Object System.Net.Security.SslStream($client.GetStream(), $false)
        try {
            $stream.ReadTimeout = $TimeoutMs
            $stream.WriteTimeout = $TimeoutMs
            $stream.AuthenticateAsClient($HostName)
            return [ordered]@{ tcp = $true; tls = $stream.IsAuthenticated; error = $null }
        }
        finally {
            $stream.Dispose()
        }
    }
    catch {
        return [ordered]@{ tcp = $client.Connected; tls = $false; error = $_.Exception.Message }
    }
    finally {
        $client.Close()
    }
}

function Test-DirectHttps {
    param([string]$HostName, [string]$Address, [string]$Url)
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if (-not $curl) { return [ordered]@{ reached = $false; status = $null; error = "curl.exe not found" } }
    $arguments = @(
        "--silent", "--show-error", "--max-time", "12",
        "--output", "NUL", "--write-out", "%{http_code}",
        "--resolve", "${HostName}:443:$Address", $Url
    )
    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& $curl.Source @arguments 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
    $statusText = @($output | Where-Object { $_ -match '^\d{3}$' } | Select-Object -Last 1)
    $status = if ($statusText.Count) { [int]$statusText[0] } else { $null }
    return [ordered]@{
        reached = ($exitCode -eq 0 -and $null -ne $status)
        status = $status
        error = if ($exitCode -eq 0) { $null } else { "curl-exit-$exitCode" }
    }
}

function Select-ValidatedAddress {
    param([System.Collections.IDictionary]$Target)
    foreach ($address in @(Resolve-PublicCandidates -HostName $Target.host)) {
        $transport = Test-DirectTcpTls -HostName $Target.host -Address $address
        if (-not $transport.tcp -or -not $transport.tls) {
            Write-Host "Rejected $($Target.host) ${address}: TCP/TLS validation failed."
            continue
        }
        $https = Test-DirectHttps -HostName $Target.host -Address $address -Url $Target.url
        if ($https.reached -and $https.status -in @(200, 401, 403, 404)) {
            Write-Host "Validated $($Target.host) ${address}: HTTPS $($https.status)."
            return [ordered]@{ host = $Target.host; address = $address; httpsStatus = $https.status }
        }
        Write-Host "Rejected $($Target.host) ${address}: HTTPS validation failed."
    }
    return $null
}

function Select-ProvidedAddress {
    param([System.Collections.IDictionary]$Target)
    $address = [string]$Target.address
    if (-not (Test-PublicIPv4 -Address $address)) {
        Write-Host "Rejected $($Target.host) ${address}: not a public IPv4 address."
        return $null
    }
    $transport = Test-DirectTcpTls -HostName $Target.host -Address $address
    if (-not $transport.tcp -or -not $transport.tls) {
        Write-Host "Rejected $($Target.host) ${address}: TCP/TLS validation failed."
        return $null
    }
    $https = Test-DirectHttps -HostName $Target.host -Address $address -Url $Target.url
    if (-not $https.reached -or $https.status -notin @(200, 401, 403, 404)) {
        Write-Host "Rejected $($Target.host) ${address}: HTTPS validation failed."
        return $null
    }
    Write-Host "Validated fixed bypass $($Target.host) ${address}: HTTPS $($https.status)."
    return [ordered]@{ host = $Target.host; address = $address; httpsStatus = $https.status }
}

function Get-WatchbaneBlock {
    param([string]$Content)
    $pattern = '(?ms)^' + [regex]::Escape($beginMarker) + '.*?^' + [regex]::Escape($endMarker) + '\s*'
    $match = [regex]::Match($Content, $pattern)
    if ($match.Success) { return $match.Value.TrimEnd("`r", "`n") }
    return ""
}

function Remove-WatchbaneBlock {
    param([string]$Content)
    $pattern = '(?ms)^' + [regex]::Escape($beginMarker) + '.*?^' + [regex]::Escape($endMarker) + '\s*'
    return ([regex]::Replace($Content, $pattern, "")).TrimEnd("`r", "`n") + "`r`n"
}

function New-OverrideBlock {
    param([object[]]$Entries)
    $lines = @(
        $beginMarker,
        "# TEMP TMDb diagnostic",
        "# Applied: $((Get-Date).ToString('o'))",
        "# Revalidate after: $MaxAgeHours hours"
    )
    foreach ($entry in $Entries) { $lines += "$($entry.address) $($entry.host)" }
    $lines += $endMarker
    return $lines -join "`r`n"
}

function Save-HostsBackup {
    param([string]$Content)
    New-Item -ItemType Directory -Force -Path $backupDirectory | Out-Null
    $path = Join-Path $backupDirectory "hosts-$(Get-Date -Format 'yyyyMMdd-HHmmss').bak"
    [System.IO.File]::WriteAllText($path, $Content, (New-Object System.Text.UTF8Encoding($false)))
    return $path
}

function Write-HostsContent {
    param([string]$Content)
    $tempPath = "$hostsPath.watchbane.tmp"
    [System.IO.File]::WriteAllText($tempPath, $Content, (New-Object System.Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $tempPath -Destination $hostsPath -Force
}

function Confirm-Action {
    param([string]$Expected, [string]$Message)
    if ($Yes) { return $true }
    Write-Warning $Message
    return (Read-Host "Type '$Expected' to continue") -ceq $Expected
}

function Flush-Dns {
    & ipconfig.exe /flushdns | Out-Host
    if ($LASTEXITCODE -ne 0) { Write-Warning "ipconfig /flushdns failed with exit code $LASTEXITCODE." }
}

function Test-StateStale {
    param([datetime]$AppliedAt, [int]$Hours)
    return ((Get-Date) - $AppliedAt).TotalHours -ge $Hours
}

function Show-Status {
    $content = [System.IO.File]::ReadAllText($hostsPath)
    $block = Get-WatchbaneBlock -Content $content
    Write-Output "Hosts path: $hostsPath"
    Write-Output "Watchbane block present: $([bool]$block)"
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $age = (Get-Date) - [datetime]$state.appliedAt
        Write-Output "Applied at: $($state.appliedAt)"
        Write-Output "Age hours: $([math]::Round($age.TotalHours, 1))"
        if (Test-StateStale -AppliedAt ([datetime]$state.appliedAt) -Hours $MaxAgeHours) {
            Write-Warning "The CDN addresses are stale. Re-run -Preview before keeping or reapplying this override."
        }
    }
    Write-Warning "CDN IPs can change. A hosts override is temporary; prefer repairing DNS or the network route."
}

if ($SelfTest) {
    $sample = "127.0.0.1 localhost`r`n$beginMarker`r`n203.0.113.10 api.themoviedb.org`r`n$endMarker`r`n10.0.0.2 custom.local`r`n"
    $block = Get-WatchbaneBlock -Content $sample
    if (-not $block -or $block -notmatch 'api\.themoviedb\.org') { throw "Self-test: existing block was not detected." }
    $removed = Remove-WatchbaneBlock -Content $sample
    if ($removed -match [regex]::Escape($beginMarker)) { throw "Self-test: marked block was not removed." }
    if ($removed -notmatch '127\.0\.0\.1 localhost' -or $removed -notmatch '10\.0\.0\.2 custom\.local') {
        throw "Self-test: unrelated hosts lines were changed."
    }
    if (-not (Test-StateStale -AppliedAt (Get-Date).AddHours(-25) -Hours 24)) {
        throw "Self-test: stale override was not detected."
    }
    $testBlock = New-OverrideBlock -Entries @(
        [ordered]@{ host = "api.themoviedb.org"; address = "3.173.161.72" },
        [ordered]@{ host = "www.themoviedb.org"; address = "18.239.105.83" }
    )
    if ($testBlock -notmatch [regex]::Escape("# TEMP TMDb diagnostic")) {
        throw "Self-test: diagnostic comment is missing."
    }
    if ($testBlock -notmatch '3\.173\.161\.72 api\.themoviedb\.org' -or
        $testBlock -notmatch '18\.239\.105\.83 www\.themoviedb\.org') {
        throw "Self-test: fixed bypass entries are incomplete."
    }
    $backup = Save-HostsBackup -Content $sample
    if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) { throw "Self-test: backup was not created." }
    $restoreTarget = Join-Path $backupDirectory "selftest-restored-hosts"
    Copy-Item -LiteralPath $backup -Destination $restoreTarget -Force
    if ([System.IO.File]::ReadAllText($restoreTarget) -ne $sample) { throw "Self-test: backup restore did not preserve content." }
    Remove-Item -LiteralPath $restoreTarget -Force
    Write-Output "SELFTEST OK"
    exit 0
}

if ($Status) { Show-Status; exit 0 }

$currentContent = [System.IO.File]::ReadAllText($hostsPath)
$currentBlock = Get-WatchbaneBlock -Content $currentContent

if ($Restore) {
    if (-not (Test-IsAdministrator)) { throw "Administrator rights are required to restore hosts." }
    if (-not $BackupPath -and (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        $BackupPath = [string](Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json).backupPath
    }
    if (-not $BackupPath -or -not (Test-Path -LiteralPath $BackupPath -PathType Leaf)) { throw "Hosts backup was not found." }
    Write-Output "Restore backup: $BackupPath"
    if (-not (Confirm-Action -Expected "RESTORE HOSTS" -Message "This restores the complete hosts backup created before Watchbane changed its marked block.")) { exit 5 }
    Copy-Item -LiteralPath $BackupPath -Destination $hostsPath -Force
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    Flush-Dns
    Write-Output "Hosts restored."
    exit 0
}

if ($Remove) {
    Write-Output "Current Watchbane block:"
    Write-Output $(if ($currentBlock) { $currentBlock } else { "<absent>" })
    Write-Output "Proposed Watchbane block: <absent>"
    if (-not $currentBlock) { Write-Output "Nothing to remove."; exit 0 }
    if (-not (Test-IsAdministrator)) { throw "Administrator rights are required to change hosts." }
    if (-not (Confirm-Action -Expected "REMOVE HOSTS" -Message "Only the marked Watchbane block will be removed; other user lines remain unchanged.")) { exit 5 }
    $BackupPath = Save-HostsBackup -Content $currentContent
    Write-HostsContent -Content (Remove-WatchbaneBlock -Content $currentContent)
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    Flush-Dns
    Write-Output "Watchbane block removed. Backup: $BackupPath"
    exit 0
}

$validated = @()
foreach ($target in $requiredHosts) {
    $entry = if ($TryBypass) {
        Select-ProvidedAddress -Target $target
    }
    else {
        Select-ValidatedAddress -Target $target
    }
    if ($null -eq $entry) { throw "No currently validated public IPv4 was found for $($target.host). Hosts was not changed." }
    $validated += $entry
}
$newBlock = New-OverrideBlock -Entries $validated
Write-Warning "CDN IPs can change. This is a temporary diagnostic workaround; prefer repairing DNS or the network route."
Write-Output "Current Watchbane block:"
Write-Output $(if ($currentBlock) { $currentBlock } else { "<absent>" })
Write-Output "Proposed Watchbane block:"
Write-Output $newBlock

if ($Preview) {
    Write-Output "Preview only. Hosts was not changed."
    exit 0
}

if (-not (Test-IsAdministrator)) { throw "Administrator rights are required to change hosts." }
if (-not (Confirm-Action -Expected "APPLY HOSTS" -Message "A timestamped backup will be created before replacing only the marked Watchbane block.")) {
    Write-Output "Cancelled. Hosts was not changed."
    exit 5
}
$BackupPath = Save-HostsBackup -Content $currentContent
$withoutBlock = Remove-WatchbaneBlock -Content $currentContent
$updatedContent = $withoutBlock.TrimEnd("`r", "`n") + "`r`n`r`n" + $newBlock + "`r`n"
Write-HostsContent -Content $updatedContent
[ordered]@{
    schemaVersion = 1
    mode = $(if ($TryBypass) { "fixed-bypass" } else { "trusted-dns" })
    appliedAt = (Get-Date).ToString("o")
    maxAgeHours = $MaxAgeHours
    backupPath = $BackupPath
    entries = $validated
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $statePath -Encoding UTF8
Flush-Dns

$diagnostic = Join-Path $PSScriptRoot "tmdb-network-diagnose.ps1"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $diagnostic -NoVpn -Label "after-hosts-override" -OutputDirectory $OutputDirectory
$latest = Get-ChildItem -LiteralPath $OutputDirectory -Filter "tmdb-network-no-vpn-after-hosts-override-*.json" -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
$healthy = $false
if ($latest) {
    $post = Get-Content -LiteralPath $latest.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $healthy = [bool]$post.networkPathAvailable -and [bool]$post.posterHostAvailable
}
if (-not $healthy) {
    Write-Warning "Post-change validation failed. Restoring the backup automatically."
    Copy-Item -LiteralPath $BackupPath -Destination $hostsPath -Force
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    Flush-Dns
    throw "Hosts override failed validation and was rolled back."
}
Write-Output "Temporary hosts override applied and validated. Backup: $BackupPath"
exit 0
