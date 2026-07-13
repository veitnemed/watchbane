[CmdletBinding()]
param(
    [switch]$NoVpn,
    [switch]$Vpn,
    [string]$Label = "",
    [string]$OutputDirectory = "",
    [string]$TokenPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($NoVpn -and $Vpn) {
    throw "Use either -NoVpn or -Vpn, not both."
}

$script:ApiHost = "api.themoviedb.org"
$script:PosterHost = "image.tmdb.org"
$script:DnsServers = @("1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4")
$script:Mode = if ($NoVpn) { "no-vpn" } elseif ($Vpn) { "vpn" } else { "unlabelled" }
$script:StartedAt = Get-Date

function Get-SafeLabel {
    param([string]$Value)
    $safe = ($Value -replace '[^A-Za-z0-9._-]', '-') -replace '-+', '-'
    return $safe.Trim('-')
}

function Get-AddressClass {
    param([string]$Address)
    try {
        $ip = [System.Net.IPAddress]::Parse($Address)
    }
    catch {
        return "invalid"
    }
    if ([System.Net.IPAddress]::IsLoopback($ip)) { return "loopback" }
    if ($ip.Equals([System.Net.IPAddress]::Any) -or $ip.Equals([System.Net.IPAddress]::IPv6Any)) {
        return "unspecified"
    }
    if ($ip.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork) {
        $bytes = $ip.GetAddressBytes()
        if ($bytes[0] -eq 169 -and $bytes[1] -eq 254) { return "link-local" }
        if ($bytes[0] -eq 10) { return "private" }
        if ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) { return "private" }
        if ($bytes[0] -eq 192 -and $bytes[1] -eq 168) { return "private" }
        return "public-ipv4"
    }
    if ($ip.IsIPv6LinkLocal) { return "link-local" }
    if ($ip.IsIPv6SiteLocal -or $ip.ToString().StartsWith("fc") -or $ip.ToString().StartsWith("fd")) {
        return "private"
    }
    return "public-ipv6"
}

function Convert-Addresses {
    param([object[]]$Addresses)
    return @($Addresses | ForEach-Object {
        $text = [string]$_
        [ordered]@{ address = $text; classification = Get-AddressClass -Address $text }
    })
}

function Get-SystemDnsResult {
    param([string]$HostName)
    $started = Get-Date
    try {
        $addresses = @([System.Net.Dns]::GetHostAddresses($HostName) | ForEach-Object { $_.IPAddressToString } | Sort-Object -Unique)
        return [ordered]@{
            ok = ($addresses.Count -gt 0)
            source = "System.Net.Dns"
            host = $HostName
            addresses = Convert-Addresses -Addresses $addresses
            error = $null
            elapsedMs = [math]::Round(((Get-Date) - $started).TotalMilliseconds, 1)
        }
    }
    catch {
        $kind = if ($_.Exception.InnerException -and $_.Exception.InnerException.SocketErrorCode -eq "HostNotFound") { "nxdomain" } else { "dns-failed" }
        return [ordered]@{
            ok = $false
            source = "System.Net.Dns"
            host = $HostName
            addresses = @()
            error = $kind
            details = $_.Exception.Message
            elapsedMs = [math]::Round(((Get-Date) - $started).TotalMilliseconds, 1)
        }
    }
}

function Get-NslookupResult {
    param([string]$HostName, [string]$Server = "")
    $started = Get-Date
    $arguments = @($HostName)
    if ($Server) { $arguments += $Server }
    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $lines = @(& nslookup.exe @arguments 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
    $addresses = @()
    foreach ($line in $lines) {
        foreach ($match in [regex]::Matches($line, '(?<![0-9A-Fa-f:])(?:\d{1,3}\.){3}\d{1,3}(?![0-9])|(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![0-9A-Fa-f:])')) {
            $candidate = $match.Value.Trim()
            $parsed = $null
            if ([System.Net.IPAddress]::TryParse($candidate, [ref]$parsed) -and $candidate -ne $Server) {
                $addresses += $parsed.IPAddressToString
            }
        }
    }
    $addresses = @($addresses | Sort-Object -Unique)
    $joined = ($lines -join "`n")
    $errorKind = $null
    if ($joined -match '(?i)non-existent domain|NXDOMAIN|can.t find') { $errorKind = "nxdomain" }
    elseif ($joined -match '(?i)timed out') { $errorKind = "timeout" }
    elseif ($joined -match '(?i)server failed|no response from server') { $errorKind = "dns-server-unavailable" }
    elseif ($exitCode -ne 0 -or $addresses.Count -eq 0) { $errorKind = "dns-failed" }
    return [ordered]@{
        ok = ($errorKind -eq $null -and $addresses.Count -gt 0)
        source = if ($Server) { "nslookup:$Server" } else { "nslookup:system" }
        host = $HostName
        addresses = Convert-Addresses -Addresses $addresses
        error = $errorKind
        exitCode = $exitCode
        elapsedMs = [math]::Round(((Get-Date) - $started).TotalMilliseconds, 1)
    }
}

function Test-Tcp443 {
    param([string]$HostName, [int]$TimeoutMs = 7000)
    $started = Get-Date
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($HostName, 443, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
            return [ordered]@{ ok = $false; host = $HostName; port = 443; error = "timeout"; elapsedMs = [math]::Round(((Get-Date) - $started).TotalMilliseconds, 1) }
        }
        $client.EndConnect($async)
        return [ordered]@{ ok = $true; host = $HostName; port = 443; error = $null; elapsedMs = [math]::Round(((Get-Date) - $started).TotalMilliseconds, 1) }
    }
    catch {
        return [ordered]@{ ok = $false; host = $HostName; port = 443; error = "connect-failed"; details = $_.Exception.Message; elapsedMs = [math]::Round(((Get-Date) - $started).TotalMilliseconds, 1) }
    }
    finally {
        $client.Close()
    }
}

function Read-LocalToken {
    param([string]$RequestedPath)
    $candidates = @()
    if ($RequestedPath) { $candidates += $RequestedPath }
    $candidates += @(
        (Join-Path (Get-Location) "local_tocen.txt"),
        (Join-Path (Get-Location) "local_token.txt")
    )
    $selected = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $selected) { return [ordered]@{ present = $false; suffix = ""; value = ""; sourceName = "" } }
    $line = Get-Content -LiteralPath $selected -Encoding UTF8 | Where-Object { $_.Trim().Length -gt 0 } | Select-Object -First 1
    $value = ([string]$line).Trim([char]0xFEFF).Trim()
    $value = ($value -replace '^(?i)Bearer\s+', '').Trim()
    $suffix = if ($value.Length -le 4) { $value } else { $value.Substring($value.Length - 4) }
    return [ordered]@{ present = ($value.Length -gt 0); suffix = $suffix; value = $value; sourceName = [System.IO.Path]::GetFileName([string]$selected) }
}

function Test-HttpsEndpoint {
    param([string]$Url, [string]$Token = "", [int]$TimeoutMs = 10000, [switch]$DisableProxy)
    $started = Get-Date
    try {
        $request = [System.Net.HttpWebRequest]::Create($Url)
        $request.Method = "GET"
        $request.Timeout = $TimeoutMs
        $request.ReadWriteTimeout = $TimeoutMs
        if ($DisableProxy) { $request.Proxy = $null }
        $request.UserAgent = "Watchbane-TMDb-Diagnostics/1"
        $request.Accept = "application/json,image/*,*/*"
        if ($Token) { $request.Headers["Authorization"] = "Bearer $Token" }
        $response = $request.GetResponse()
        try { $status = [int]$response.StatusCode } finally { $response.Close() }
        return [ordered]@{ reached = $true; tls = $true; status = $status; error = $null; elapsedMs = [math]::Round(((Get-Date) - $started).TotalMilliseconds, 1) }
    }
    catch [System.Net.WebException] {
        $exception = $_.Exception
        if ($exception.Response) {
            $status = [int]$exception.Response.StatusCode
            $exception.Response.Close()
            return [ordered]@{ reached = $true; tls = $true; status = $status; error = if ($status -in @(200, 401, 403, 404)) { $null } else { "http-error" }; elapsedMs = [math]::Round(((Get-Date) - $started).TotalMilliseconds, 1) }
        }
        $kind = switch ([string]$exception.Status) {
            "NameResolutionFailure" { "dns-failed" }
            "ConnectFailure" { "tcp-failed" }
            "TrustFailure" { "certificate-error" }
            "SecureChannelFailure" { "tls-failed" }
            "Timeout" { "timeout" }
            default { "https-failed" }
        }
        return [ordered]@{ reached = $false; tls = $false; status = $null; error = $kind; details = $exception.Message; elapsedMs = [math]::Round(((Get-Date) - $started).TotalMilliseconds, 1) }
    }
}

function Get-HostDiagnostic {
    param([string]$HostName, [string]$Url, [string]$Token = "")
    $systemDns = Get-SystemDnsResult -HostName $HostName
    $serverDns = @($script:DnsServers | ForEach-Object { Get-NslookupResult -HostName $HostName -Server $_ })
    return [ordered]@{
        host = $HostName
        systemDns = $systemDns
        systemNslookup = Get-NslookupResult -HostName $HostName
        trustedDns = $serverDns
        tcp443 = Test-Tcp443 -HostName $HostName
        https = Test-HttpsEndpoint -Url $Url -Token $Token
        httpsDirect = Test-HttpsEndpoint -Url $Url -Token $Token -DisableProxy
    }
}

function Get-SystemProxySummary {
    try {
        $target = [Uri]"https://api.themoviedb.org/3/configuration"
        $proxyUri = [System.Net.WebRequest]::GetSystemWebProxy().GetProxy($target)
        $configured = $null -ne $proxyUri -and $proxyUri.AbsoluteUri -ne $target.AbsoluteUri
        return [ordered]@{
            configured = $configured
            endpoint = if ($configured) { "$($proxyUri.Scheme)://$($proxyUri.Host):$($proxyUri.Port)" } else { "" }
        }
    }
    catch {
        return [ordered]@{ configured = $null; endpoint = ""; error = $_.Exception.Message }
    }
}

function Get-PrimaryFailure {
    param([System.Collections.IDictionary]$Api, [System.Collections.IDictionary]$Poster)
    $classes = @($Api.systemDns.addresses | ForEach-Object { $_.classification })
    if ($classes -contains "loopback" -or $classes -contains "unspecified") { return "dns-loopback-or-null-route" }
    if (-not $Api.systemDns.ok) { return [string]$Api.systemDns.error }
    if (-not $Api.tcp443.ok) { return "tcp-443-unavailable" }
    if (-not $Api.https.reached) { return [string]$Api.https.error }
    if ($Api.https.status -eq 401) { return "token-unauthorized" }
    if ($Api.https.status -eq 403) { return "api-forbidden" }
    if (-not $Poster.https.reached) { return "poster-host-unavailable" }
    return "none"
}

$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $root ".local\diagnostics" }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$tokenInfo = Read-LocalToken -RequestedPath $TokenPath
$api = Get-HostDiagnostic -HostName $script:ApiHost -Url "https://api.themoviedb.org/3/configuration" -Token $tokenInfo.value
$poster = Get-HostDiagnostic -HostName $script:PosterHost -Url "https://image.tmdb.org/t/p/w92"
$failure = Get-PrimaryFailure -Api $api -Poster $poster
$labelSafe = Get-SafeLabel -Value $Label
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$baseName = "tmdb-network-$($script:Mode)"
if ($labelSafe) { $baseName += "-$labelSafe" }
$baseName += "-$stamp"

$report = [ordered]@{
    schemaVersion = 1
    createdAt = (Get-Date).ToString("o")
    mode = $script:Mode
    label = $Label
    requiredHosts = @($script:ApiHost, $script:PosterHost)
    optionalHosts = @("wsrv.nl")
    refererOnlyHosts = @("www.themoviedb.org")
    token = [ordered]@{ present = $tokenInfo.present; suffix = $tokenInfo.suffix; sourceName = $tokenInfo.sourceName }
    systemProxy = Get-SystemProxySummary
    api = $api
    poster = $poster
    primaryFailure = $failure
    networkPathAvailable = ($api.https.reached -and $api.https.status -in @(200, 401, 403, 404))
    apiAuthorized = ($api.https.status -eq 200)
    posterHostAvailable = $poster.https.reached
    elapsedMs = [math]::Round(((Get-Date) - $script:StartedAt).TotalMilliseconds, 1)
}

$jsonPath = Join-Path $OutputDirectory "$baseName.json"
$textPath = Join-Path $OutputDirectory "$baseName.md"
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$summary = @(
    "# TMDb Network Diagnostics",
    "",
    "- Mode: $($report.mode)",
    "- Label: $($report.label)",
    "- Primary failure: $($report.primaryFailure)",
    "- Network path available: $($report.networkPathAvailable)",
    "- API authorized: $($report.apiAuthorized)",
    "- Poster host available: $($report.posterHostAvailable)",
    "- Token present: $($report.token.present)",
    "- Token suffix: $(if ($report.token.present) { '...' + $report.token.suffix } else { '-' })",
    "- System proxy configured: $($report.systemProxy.configured)",
    "",
    "Required hosts: api.themoviedb.org, image.tmdb.org.",
    "www.themoviedb.org is Referer-only; wsrv.nl is an optional poster fallback.",
    "No DNS, hosts, proxy or VPN settings were changed."
)
$summary | Set-Content -LiteralPath $textPath -Encoding UTF8

Write-Output "JSON report: $jsonPath"
Write-Output "Human report: $textPath"
Write-Output "Primary failure: $failure"
Write-Output "Token present: $($tokenInfo.present)$(if ($tokenInfo.present) { '; suffix: ...' + $tokenInfo.suffix } else { '' })"

if (-not $report.networkPathAvailable -or -not $report.posterHostAvailable) { exit 2 }
if ($tokenInfo.present -and -not $report.apiAuthorized) { exit 3 }
exit 0
