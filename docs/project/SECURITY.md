# Security Policy

## Supported Versions

The active `main` branch is supported.

## Reporting a Vulnerability

Please open a private security advisory on GitHub if available, or create an issue without including secrets or private data.

Do not include:

- API tokens;
- local `data/` files;
- private watched history;
- logs containing credentials.

## Secrets

TMDb/KP/API tokens must stay outside git:

- environment variables;
- `.env.local`;
- `tmdb.env`;
- local secret managers.

Runtime data under `data/` is user-owned local data and should not be committed.
