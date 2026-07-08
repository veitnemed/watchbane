# Watchbane fullscreen onboarding + dev sandbox prompt pack

Цель:
- исправить onboarding, который выглядит как маленькое окно поверх пустого приложения;
- сделать onboarding как full-window flow;
- добавить плавные переходы, красивые карточки выбора и loading screen;
- добавить безопасный dev-reset: backup, empty profile, clear candidate pool on start;
- работать с локальным TMDb token без утечки секрета;
- доводить визуал итерациями через screenshots.

Рекомендуемый запуск:

```powershell
cd "D:\VS PROJJJ\vscode projects\watchbane-codex-lab"
git switch -c experiment/fullscreen-onboarding-polish

.\.codex-onboarding-fullscreen\local_scripts\backup-runtime-data.ps1 -Repo "."
.\.codex-onboarding-fullscreen\run-codex-onboarding-queue.ps1 -Repo "." -Model "gpt-5.5" -Reasoning "high"
```

Первые 3 шага:

```powershell
.\.codex-onboarding-fullscreen\run-codex-onboarding-queue.ps1 -Repo "." -StopAfter 3
```

С API-сетью только для ручной проверки TMDb:

```powershell
.\.codex-onboarding-fullscreen\run-codex-onboarding-queue.ps1 -Repo "." -StartAt "08" -AllowNetwork
```

Откат:

```powershell
git reset --hard before-fullscreen-onboarding
```

Важно:
- не коммитить `.env`, реальные SQLite DB, screenshots, backup folders;
- dev clear должен быть явным флагом, не дефолтом;
- TMDb token не печатать в логах.
