# TMDb Network Investigation — 2026-07-13

## Outcome

The original HTTP `401` was caused by token-file parsing, not by an unavailable TMDb API. The local token was stored in dotenv assignment form (`TMDB_ACCESS_TOKEN=…`), while the diagnostic path initially treated the complete assignment as the bearer value. Watchbane and the diagnostic script now accept raw, `Bearer`, and dotenv-assignment formats without logging the secret.

The verified current session uses an active `happ-tun` / `sing-tun Tunnel` adapter and a local HTTP proxy on port `10809`. It is therefore a VPN/proxy-mode result, not a direct no-VPN measurement.

## Observed results

| Layer | API host | Poster host |
|---|---|---|
| Required hostname | `api.themoviedb.org` | `image.tmdb.org` |
| System DNS | public IPv4 observed | loopback observed |
| TCP 443 by hostname | available | direct path unavailable |
| HTTPS via system proxy | HTTP 200 with token | HTTP 404 on a minimal probe URL |
| Direct HTTPS | HTTP 200 | failed before HTTP |
| Result | API and token valid | poster CDN reachable through proxy |

HTTP 404 for the minimal poster path is expected as a reachability signal: it proves that DNS/proxy, TCP, TLS and HTTP reached the poster service without downloading a large image.

Queries sent to explicitly named public DNS servers produced mixed/intercepted answers while the tunnel was active. They cannot be treated as independent no-VPN evidence in this session.

## VPN and hosts conclusions

- API with current VPN/proxy: works.
- Poster host with current VPN/proxy: works.
- API without VPN: not measured; the user must disconnect the VPN and run the `-NoVpn` command.
- Whether VPN is required: not yet proven either way for a truly direct connection.
- Hosts override: not required for the current working path. Preview failed closed because no candidate public IPv4 passed every validation step; hosts remained unchanged.
- DNS change: not applied. The active tunnel adapter already reported Cloudflare DNS, so changing DNS was not justified.

## Host inventory

- Required API: `api.themoviedb.org`.
- Required posters: `image.tmdb.org`.
- Optional poster fallback: `wsrv.nl`.
- Referer-only, no required connection: `www.themoviedb.org`.

No permanent CDN IP is embedded in Watchbane.

## Files added or changed

- `.gitignore` — protects local token files and diagnostic reports.
- `scripts/tmdb-network-diagnose.ps1` — read-only DNS/TCP/TLS/API/poster diagnosis.
- `scripts/tmdb-network-compare.ps1` — VPN/no-VPN comparison.
- `scripts/tmdb-dns-recovery.ps1` — explicit, backed-up DNS apply/restore.
- `scripts/tmdb-hosts-override.ps1` — guarded temporary hosts preview/apply/remove/restore.
- `desktop/startup/network_tools.py` and token-gate UI — diagnostics and recovery entry points.
- `apis/tmdb_connectivity.py` — precise failure classification.
- `apis/tmdb/client.py` — safe pasted token normalization.
- `watchbane.spec` — bundles the four PowerShell tools.
- tests for connectivity, PowerShell parsing, token formats, comparison scenarios and hosts safety.
- `docs/TMDB_NETWORK_TROUBLESHOOTING.md` — operating guide and rollback instructions.

## Verification

- Windows PowerShell 5.1 parser: all four scripts pass.
- PowerShell 7 was not installed on the test machine; the scripts avoid APIs unavailable in Windows PowerShell 5.1.
- Offline targeted regression: 68 tests passed before documentation finalization.
- Native Windows token-gate screenshots were visually reviewed at application scales 0.75, 1.0 and 1.5; Segoe UI was available.
- Read-only live probe: API HTTP 200, poster endpoint HTTP 404 reachability, token accepted.
- DNS and hosts mutation actions were not executed.
- Secret scans found no token value in Git diff, staged content or generated diagnostic reports.

## Next manual experiment

1. Disconnect the VPN/proxy completely and confirm that no tunnel adapter remains active.
2. Run `tmdb-network-diagnose.ps1 -NoVpn`.
3. Reconnect the VPN and run `tmdb-network-diagnose.ps1 -Vpn`.
4. Run `tmdb-network-compare.ps1` and use its scenario conclusion.
