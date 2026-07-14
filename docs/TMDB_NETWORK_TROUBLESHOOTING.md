# TMDb Network Troubleshooting

Watchbane uses two required network hosts:

- `api.themoviedb.org` — search, Discover, details and token validation;
- `image.tmdb.org` — poster delivery.

`www.themoviedb.org` is used only as an HTTP `Referer` value and is not a required connection target. `wsrv.nl` is an optional poster fallback, not a requirement for normal API work.

## What loopback DNS means

If `api.themoviedb.org` or `image.tmdb.org` resolves to `127.0.0.0/8`, `::1` or `0.0.0.0`, the request is being directed back to the local computer or to a null route. Common causes are a DNS filter, local proxy/VPN software, security software, a hosts entry or upstream DNS substitution.

This does not prove that a VPN is required. DNS, TCP 443, TLS, HTTP, API authorization and poster delivery must be checked separately.

`ping` alone is insufficient: a CDN may ignore ICMP while HTTPS works, and a successful ping does not validate TLS, the HTTP endpoint, the token or poster delivery.

## Read-only diagnostics

On the token screen choose **TMDb connection diagnostics**. This does not change DNS, hosts, proxy or VPN settings.

The equivalent command is:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/tmdb-network-diagnose.ps1 -Label manual
```

Source-tree reports are written under `.local/diagnostics/` as JSON and Markdown. Packaged Watchbane writes them to its per-user diagnostics directory. Reports never contain the token or Authorization header; they show only token presence and at most the last four characters.

Possible failure classes include:

- `dns-loopback-or-null-route`, `nxdomain`, `dns-failed`, `timeout`;
- `tcp-443-unavailable`;
- `tls-failed`, `certificate-error`;
- `token-unauthorized`, `api-forbidden`;
- `poster-host-unavailable`.

HTTP `200` is full success. HTTP `401`, `403` and `404` still prove that DNS/TCP/TLS/HTTP reached a server; they must not be reported as a generic network outage.

## VPN versus direct connection

Watchbane never enables or disables a VPN client. Run both measurements manually:

```powershell
# Disconnect the VPN first.
powershell -ExecutionPolicy Bypass -File scripts/tmdb-network-diagnose.ps1 -NoVpn

# Connect the VPN, then run the second measurement.
powershell -ExecutionPolicy Bypass -File scripts/tmdb-network-diagnose.ps1 -Vpn

powershell -ExecutionPolicy Bypass -File scripts/tmdb-network-compare.ps1
```

Interpretation:

- public DNS plus failed TCP/TLS/HTTP without VPN and success with VPN means a VPN/proxy/alternate route is required;
- working HTTPS with `401` means the network works and the token must be checked;
- working API plus failed poster probe means `image.tmdb.org` must be diagnosed separately;
- the same failure in both modes means the VPN probably does not address the cause;
- loopback system DNS plus public independent DNS suggests DNS/DoH repair before VPN or hosts changes.

Do not label a report `-NoVpn` while a tunnel adapter or proxy is still active.

## DNS recovery

Open **Recovery tools** on the token screen. Status is read-only:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/tmdb-dns-recovery.ps1 -Status
```

Applying or restoring DNS requires an elevated console and explicit typed confirmation:

```powershell
# Proposes 1.1.1.1 and 1.0.0.1 for the active IPv4 adapter.
powershell -ExecutionPolicy Bypass -File scripts/tmdb-dns-recovery.ps1 -Apply

# Restores the latest saved DNS backup.
powershell -ExecutionPolicy Bypass -File scripts/tmdb-dns-recovery.ps1 -Restore
```

Before applying, the tool displays the adapter and current DNS servers. It creates a timestamped backup, flushes the DNS cache and reruns TMDb diagnostics. Watchbane never changes DNS during normal startup.

## Temporary hosts override

A hosts override is a last-resort diagnostic workaround because CDN addresses can change. The default action is preview-only:

On the startup token screen, **Попробовать обход** runs the guarded fixed route used by Watchbane 0.1.1-alpha.1. It validates `3.173.161.72` for `api.themoviedb.org` and `18.239.105.83` for `www.themoviedb.org` with TCP 443, correct TLS SNI and HTTPS before requesting UAC. The button then creates a backup, writes only the marked block, flushes DNS, verifies the API and poster path, and automatically restores the backup if the post-check fails.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/tmdb-hosts-override.ps1 -Preview
powershell -ExecutionPolicy Bypass -File scripts/tmdb-hosts-override.ps1 -Status
powershell -ExecutionPolicy Bypass -File scripts/tmdb-hosts-override.ps1 -TryBypass -Preview
```

Preview obtains current public IPv4 candidates through an independent DNS query and accepts an address only after direct TCP 443, TLS with correct SNI and HTTPS validation. If validation fails, hosts is not changed.

Apply, remove and restore require administrator rights and explicit typed confirmation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/tmdb-hosts-override.ps1 -Apply
powershell -ExecutionPolicy Bypass -File scripts/tmdb-hosts-override.ps1 -Remove
powershell -ExecutionPolicy Bypass -File scripts/tmdb-hosts-override.ps1 -Restore
```

Only the marked block is changed:

```text
# BEGIN WATCHBANE TEMP TMDB
# TEMP TMDb diagnostic
3.173.161.72 api.themoviedb.org
18.239.105.83 www.themoviedb.org
# END WATCHBANE TEMP TMDB
```

Other user lines remain untouched. A timestamped backup is created first. Failed post-apply validation automatically restores the backup. `Status` warns when the stored addresses are older than 24 hours.

## Token storage

The packaged app stores an accepted token in its per-user `data/.env.local`. For local diagnosis, the repository may contain either `local_tocen.txt` or `local_token.txt`. The first non-empty line may be:

- a raw token;
- `Bearer <token>`;
- `TMDB_ACCESS_TOKEN=<token>` or `TMDB_TOKEN=<token>`.

Both local token filenames are ignored by Git. Never add them to a commit, issue, report, screenshot or log.

## Complete rollback

- DNS: run `tmdb-dns-recovery.ps1 -Restore` and select the saved backup if prompted.
- Hosts block: run `tmdb-hosts-override.ps1 -Remove`.
- Full hosts backup: run `tmdb-hosts-override.ps1 -Restore`.
- Application diagnostics are read-only; delete generated local reports if no longer needed.
