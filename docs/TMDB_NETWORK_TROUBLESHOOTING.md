# Диагностика сети TMDb

Watchbane использует два обязательных сетевых хоста:

- `api.themoviedb.org` — search, Discover, details и проверка токена;
- `image.tmdb.org` — доставка постеров.

`www.themoviedb.org` используется только как значение HTTP `Referer` и не является обязательной целью соединения. `wsrv.nl` — optional poster fallback, не требование для обычной работы API.

## Что значит loopback DNS

Если `api.themoviedb.org` или `image.tmdb.org` резолвится в `127.0.0.0/8`, `::1` или `0.0.0.0`, запрос направляется обратно на локальный компьютер или в null route. Частые причины — DNS-фильтр, локальный proxy/VPN, security software, запись в hosts или подмена upstream DNS.

Это не доказывает, что нужен VPN. DNS, TCP 443, TLS, HTTP, авторизацию API и доставку постеров нужно проверять отдельно.

Одного `ping` недостаточно: CDN может игнорировать ICMP при работающем HTTPS, а успешный ping не подтверждает TLS, HTTP endpoint, токен или доставку постеров.

## Read-only диагностика

На экране токена выберите **TMDb connection diagnostics**. Это не меняет DNS, hosts, proxy или настройки VPN.

Эквивалентная команда:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/tmdb-network-diagnose.ps1 -Label manual
```

Отчёты из source-tree пишутся в `.local/diagnostics/` как JSON и Markdown. Упакованный Watchbane пишет их в свой per-user diagnostics directory. Отчёты никогда не содержат токен или Authorization header; показывают только наличие токена и максимум последние четыре символа.

Возможные классы сбоев включают:

- `dns-loopback-or-null-route`, `nxdomain`, `dns-failed`, `timeout`;
- `tcp-443-unavailable`;
- `tls-failed`, `certificate-error`;
- `token-unauthorized`, `api-forbidden`;
- `poster-host-unavailable`.

HTTP `200` — полный успех. HTTP `401`, `403` и `404` всё равно доказывают, что DNS/TCP/TLS/HTTP дошли до сервера; их нельзя сообщать как общий network outage.

## VPN против прямого соединения

Watchbane никогда не включает и не выключает VPN-клиент. Оба измерения выполняйте вручную:

```powershell
# Disconnect the VPN first.
powershell -ExecutionPolicy Bypass -File scripts/tmdb-network-diagnose.ps1 -NoVpn

# Connect the VPN, then run the second measurement.
powershell -ExecutionPolicy Bypass -File scripts/tmdb-network-diagnose.ps1 -Vpn

powershell -ExecutionPolicy Bypass -File scripts/tmdb-network-compare.ps1
```

Интерпретация:

- публичный DNS плюс сбой TCP/TLS/HTTP без VPN и успех с VPN означают, что нужен VPN/proxy/alternate route;
- работающий HTTPS с `401` означает, что сеть работает и нужно проверить токен;
- работающий API плюс сбой poster probe означают, что `image.tmdb.org` нужно диагностировать отдельно;
- один и тот же сбой в обоих режимах означает, что VPN, скорее всего, не устраняет причину;
- loopback system DNS плюс рабочий независимый публичный DNS указывают на ремонт DNS/DoH до смены VPN или hosts.

Не помечайте отчёт как `-NoVpn`, пока всё ещё активен tunnel adapter или proxy.

## Восстановление DNS

Откройте **Recovery tools** на экране токена. Статус — read-only:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/tmdb-dns-recovery.ps1 -Status
```

Применение или восстановление DNS требует elevated console и явного подтверждения вводом:

```powershell
# Proposes 1.1.1.1 and 1.0.0.1 for the active IPv4 adapter.
powershell -ExecutionPolicy Bypass -File scripts/tmdb-dns-recovery.ps1 -Apply

# Restores the latest saved DNS backup.
powershell -ExecutionPolicy Bypass -File scripts/tmdb-dns-recovery.ps1 -Restore
```

Перед применением инструмент показывает adapter и текущие DNS servers. Создаёт timestamped backup, сбрасывает DNS cache и повторно запускает TMDb diagnostics. Watchbane никогда не меняет DNS при обычном startup.

## Временный hosts override

Hosts override — диагностический обход последнего resort, потому что адреса CDN могут меняться. Действие по умолчанию — только preview:

На стартовом экране токена **Попробовать обход** запускает guarded fixed route, используемый Watchbane 0.1.1-alpha.1. Он проверяет `3.173.161.72` для `api.themoviedb.org` и `18.239.105.83` для `www.themoviedb.org` по TCP 443, корректному TLS SNI и HTTPS до запроса UAC. Затем кнопка создаёт backup, пишет только помеченный блок, сбрасывает DNS, проверяет API и путь постеров и автоматически восстанавливает backup, если post-check не прошёл.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/tmdb-hosts-override.ps1 -Preview
powershell -ExecutionPolicy Bypass -File scripts/tmdb-hosts-override.ps1 -Status
powershell -ExecutionPolicy Bypass -File scripts/tmdb-hosts-override.ps1 -TryBypass -Preview
```

Preview получает текущие публичные IPv4-кандидаты через независимый DNS query и принимает адрес только после прямой проверки TCP 443, TLS с корректным SNI и HTTPS. Если валидация не прошла, hosts не меняется.

Apply, remove и restore требуют права администратора и явное подтверждение вводом:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/tmdb-hosts-override.ps1 -Apply
powershell -ExecutionPolicy Bypass -File scripts/tmdb-hosts-override.ps1 -Remove
powershell -ExecutionPolicy Bypass -File scripts/tmdb-hosts-override.ps1 -Restore
```

Меняется только помеченный блок:

```text
# BEGIN WATCHBANE TEMP TMDB
# TEMP TMDb diagnostic
3.173.161.72 api.themoviedb.org
18.239.105.83 www.themoviedb.org
# END WATCHBANE TEMP TMDB
```

Остальные пользовательские строки не трогаются. Сначала создаётся timestamped backup. Неудачная post-apply validation автоматически восстанавливает backup. `Status` предупреждает, когда сохранённые адреса старше 24 часов.

## Хранение токена

Упакованное приложение хранит принятый токен в своём per-user `data/.env.local`. Для локальной диагностики в репозитории может быть либо `local_tocen.txt`, либо `local_token.txt`. Первая непустая строка может быть:

- сырой токен;
- `Bearer <token>`;
- `TMDB_ACCESS_TOKEN=<token>` или `TMDB_TOKEN=<token>`.

Оба локальных имени файлов токена игнорируются Git. Никогда не добавляйте их в commit, issue, отчёт, скриншот или лог.

## Полный откат

- DNS: выполните `tmdb-dns-recovery.ps1 -Restore` и выберите сохранённый backup, если будет запрос.
- Hosts block: выполните `tmdb-hosts-override.ps1 -Remove`.
- Полный hosts backup: выполните `tmdb-hosts-override.ps1 -Restore`.
- Диагностика приложения — read-only; удалите сгенерированные локальные отчёты, если они больше не нужны.
