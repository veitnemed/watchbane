# Чеклист публикации на GitHub

То, что нельзя полностью настроить только файлами в репозитории.

## Настройки репозитория

- Добавить description: `Local-first PyQt app for watched titles and candidate recommendations`.
- Добавить website, если позже появится demo/video.
- Добавить topics:
  - `python`
  - `pyqt6`
  - `tmdb`
  - `watchlist`
  - `recommendation-system`
  - `local-first`
  - `desktop-app`
  - `movie-database`
  - `series-tracker`
- Включить Issues.
- Включить Discussions, если нужен публичный feedback.
- Защитить `main` после первого публичного релиза.

## Визуалы

- Добавить 2–4 скриншота в `docs/assets/screens/`.
- Использовать один скриншот как GitHub social preview.
- Скриншоты Watchbane:
  - watched list + detail card;
  - candidate filters;
  - candidate detail card;
  - settings tab.

## Первый публичный релиз

- Идентичность релиза: `Watchbane 0.1.1-alpha.1 — Open Route`.
- Recommendation engine: `ReDeck v0.1.0`.
- Тег `v0.1.1-alpha.1`.
- Приложить `Watchbane-0.1.1-alpha.1-windows-x64.zip` и его SHA-256 checksum.
- Написать release notes с:
  - что работает сейчас;
  - что local-only;
  - что требует TMDb token;
  - известные ограничения.

## Cleanup README перед публичным push

- Убедиться, что badges в README указывают на `veitnemed/watchbane`.
- Добавить скриншоты, когда они есть.
- Убедиться, что выбор license намеренный.
