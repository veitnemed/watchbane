# Detached TMDb operator dry run

These commands do not contact TMDb, load credentials, touch a Watchbane
profile, export synopses, or create a search catalog. Run from the repository
root. The dry run only reads caller-supplied local files and prints counts.

```sh
python -m tools.qa.rehearse_tmdb_hydration plan \
  --export-date 2026-01-10 \
  --movie /your/path/movie_ids_01_10_2026.json.gz \
  --tv /your/path/tv_series_ids_01_10_2026.json.gz \
  --per-media-limit 100
```

Optional `--cohort COUNT INDEX` applies a fixed typed ID partition (index
starts at zero). Output includes source counts and compressed SHA-256 values,
a typed queue SHA-256 and per-media planned counts. IDs are not descriptions;
the planner does not verify origin, rights or any live API behavior.

For an offline restart drill, choose a **new, disposable directory** whose
parent exists and which only you control:

```sh
python -m tools.qa.rehearse_tmdb_hydration rehearse --checkpoint-dir ./tmdb-rehearsal
python -m tools.qa.rehearse_tmdb_hydration rehearse --checkpoint-dir ./tmdb-rehearsal --resume
```

The first process uses deterministic invented gzip files in temporary storage
and serves in-memory HTTP fixture responses to the detached transport. It
commits one item, then exits after a fixture `429` interrupts the next item
during its English fallback. This expected interruption is reported in JSON
and is not a command execution error. The second process verifies and reads
that checkpoint, retries the interrupted title from Russian, and resumes the
rest without re-fetching the completed title. It distinguishes missing
descriptions from typed unavailable resources and reports modeled HTTP
attempts, terminal counts, and audit totals. A third invocation with
`--resume` should do zero work. Requested locale does not prove text language.

Only the explicitly selected disposable checkpoint persists. The restart
drill does not support arbitrary SQLite databases or sidecar recovery and is
not authorization to fetch, store, or distribute real TMDb data. A live pilot
still requires authorized provider access and confirmed terms for the
intended retrieval, storage, indexing, and serving.

## Optional mixed movie and TV prefix

Without a schedule option, the original plans and manifests are unchanged:
all selected movies precede all selected series. Add `--interleave` to `plan`
to alternate one movie then one series while both queues have entries. It
preserves per-type sample order, caps, and optional cohort selection; it does
not add eligible series when there were none. Titles can consume different
numbers of locale requests, so this is a mixed **title** prefix, not equal
HTTP quota consumption or a coverage guarantee.

An interleaved checkpoint pins a distinct, versioned schedule even when
its final typed queue happens to match the original. Start a separate drill
and use the same flag on both commands:

```sh
python -m tools.qa.rehearse_tmdb_hydration rehearse --checkpoint-dir ./tmdb-mixed --interleave
python -m tools.qa.rehearse_tmdb_hydration rehearse --checkpoint-dir ./tmdb-mixed --interleave --resume
```

For this synthetic schedule the first process commits one movie and one
series before the exact same fixture 429; the next process attempts only the
pending movie (Russian then English) and the pending series (Russian). Changing
the schedule flag during a resume refuses the existing database without writes.
