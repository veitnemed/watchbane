# Detached TMDb Details microprobe

This is an operator-only POSIX diagnostic, not a catalog import, release step,
or license clearance. Do not run it until the account, source exports, and
intended private retrieval, storage and evaluation are all authorized.
Successful live use has **not** been verified. No client or CI calls it.

Prepare the dated local movie and TV [TMDb Daily ID Exports](https://developer.themoviedb.org/docs/daily-id-exports).
Rows with missing or unknown adult eligibility are intentionally refused for
selection; appearing in a normal export is not evidence of `adult: false`.
The first command is
read-only apart from your shell redirection and does not load credentials
or make HTTP requests. The manifest commits to both exact compressed sources
and the two ordered **typed** IDs; it does not print those IDs or descriptions.

```sh
python -m tools.qa.live_tmdb_microprobe manifest \
  --export-date YYYY-MM-DD --movie /path/movie_ids_MM_DD_YYYY.json.gz \
  --tv /path/tv_series_ids_MM_DD_YYYY.json.gz > /private/selector.json
```

Review and independently approve the exact manifest and the value of its
`queue_sha256`; pin the manifest's full-file SHA-256 as well. A toy or
regenerated manifest is not evidence of source provenance or permission.
Provision the operator's authorized bearer (see [TMDb application authentication](https://developer.themoviedb.org/docs/authentication-application))
locally as a regular owner-only
file (0400 or 0600), never via the conversation, a command argument value,
an environment variable, or a repository. Only pass the file **path**.

```sh
python -m tools.qa.live_tmdb_microprobe run --confirm-live-rights \
  --export-date YYYY-MM-DD --movie /path/movie_ids_MM_DD_YYYY.json.gz \
  --tv /path/tv_series_ids_MM_DD_YYYY.json.gz \
  --manifest /private/selector.json --manifest-sha256 APPROVED_MANIFEST_HASH \
  --queue-sha256 APPROVED_QUEUE_HASH --bearer-file /private/tmdb-bearer \
  --checkpoint-dir /private/fresh-unused-directory
```

Replace the hash placeholders before running. This command requires a new
directory in an existing owner-controlled parent. It performs at most four
attempts against the two pinned `https://api.themoviedb.org/3/{movie|tv}/{id}`
resources (RU then optional EN). It uses the detached transport without
redirects, proxy or automatic retries; 401, 403 and 429 stop immediately.
No export, title output, provider error body, or credentials are written or
logged. The explicitly chosen disposable SQLite checkpoint **does** retain
private title metadata for the probe and has mode 0600 in a 0700 directory.
Do not put it under version control or publish it. There is no resume,
migration or overwrite. A nonterminal run exits 1; a preflight refusal exits 2.
A successful report does not prove catalog coverage or synopsis language.

Offline tests exercise the full command path via injected HTTP responses;
they do not establish permission or live API availability.
