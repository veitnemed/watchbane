param(
    [ValidateSet("cloudflare-google", "google", "dhcp")]
    [string]$Mode = "cloudflare-google"
)

$InterfaceIndex = 20

if ($Mode -eq "dhcp") {
    Set-DnsClientServerAddress -InterfaceIndex $InterfaceIndex -ResetServerAddresses
} elseif ($Mode -eq "google") {
    Set-DnsClientServerAddress -InterfaceIndex $InterfaceIndex -ServerAddresses @("8.8.8.8", "8.8.4.4")
} else {
    Set-DnsClientServerAddress -InterfaceIndex $InterfaceIndex -ServerAddresses @("1.1.1.1", "8.8.8.8")
}

ipconfig /flushdns
Get-DnsClientServerAddress -InterfaceIndex $InterfaceIndex -AddressFamily IPv4 |
    Select-Object InterfaceIndex, InterfaceAlias, ServerAddresses
Resolve-DnsName api.themoviedb.org
