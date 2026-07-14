# TMDb Network Investigation — 2026-07-13/14

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
- Fixed hosts workaround: the user-supplied API and website endpoints passed direct TCP/TLS/HTTPS validation and were applied through the guarded startup flow on 2026-07-14.
- DNS change: not applied. The active tunnel adapter already reported Cloudflare DNS, so changing DNS was not justified.

## Host inventory

- Required API: `api.themoviedb.org`.
- Required posters: `image.tmdb.org`.
- Optional poster fallback: `wsrv.nl`.
- Referer-only, no required connection: `www.themoviedb.org`.

Watchbane 0.1.1-alpha.1 includes two explicit temporary diagnostic addresses for the user-triggered **Попробовать обход** flow. They are never applied silently: validation, confirmation, UAC, backup and automatic rollback are mandatory.

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
- Final Watchbane 0.1.1-alpha.1 regression: 1616 tests passed, 1 skipped.
- Final targeted token-gate/PowerShell regression after adding the VPN matrix: 30 tests passed.
- Native Windows token-gate screenshots were visually reviewed at application scales 0.75, 1.0 and 1.5; Segoe UI was available.
- The recovery-tools dialog was visually reviewed at scale 1.0; all VPN, DNS and hosts actions fit without clipping.
- Read-only live probe: API HTTP 200, poster endpoint HTTP 404 reachability, token accepted.
- Native Qt GUI smoke inserted the complete local dotenv-style token into the masked field, invoked the standard validation worker and observed the token gate `passed` signal. The smoke used an isolated temporary runtime.
- The fixed hosts action was executed through UAC. A timestamped backup and state file were created; the marked block was present after apply; API authorization and poster reachability both passed.
- The native Qt token-gate flow was then exercised end-to-end: visible window, masked `local_tocen` insertion, bypass button, UAC, token validation and `passed=True` without timeout.
- Secret scans found no token value in Git diff, staged content or generated diagnostic reports.

## Next manual experiment

1. Disconnect the VPN/proxy completely and confirm that no tunnel adapter remains active.
2. Run `tmdb-network-diagnose.ps1 -NoVpn`.
3. Reconnect the VPN and run `tmdb-network-diagnose.ps1 -Vpn`.
4. Run `tmdb-network-compare.ps1` and use its scenario conclusion.
