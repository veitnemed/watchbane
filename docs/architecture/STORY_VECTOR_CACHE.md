# Profile-local passage cache — 2026-11-19

## Scope and privacy

This increment changes persistence/performance only, not retrieval, ranking, evidence extraction or the existing library schema. Previous source ZIP/patch remain immutable. The original source preview has no disk vector cache; this increment adds one.

`create_story_search` wraps the verified local E5 encoder with `CachedPassageEncoder`. Cache lives at `storage.profiles.get_active_data_dir()/story_vectors_v1/<namespace>/`. This is the active main/sandbox/named profile data directory, not a shared model directory or global cache. The RAM index key now includes active profile as well as model path/documents. Catalog read paths do not modify candidate tables; derived vector writes happen explicitly while constructing/searching the story engine.

Only passage vectors (full descriptions and the final cards' source sentences) persist. Queries bypass disk caching. No plaintext synopsis, title, query, API token or user identity is stored. Embeddings and text hashes are still derived private information, are not encrypted, and must remain in the user's profile. No network or telemetry is introduced. Profile copies/backups may include this disposable directory. Delete `story_vectors_v1` with the app closed to remove derived vectors; the next search reconstructs them. Old changed/deleted descriptions are unreachable by current retrieval but remain on disk until cache deletion; automatic garbage collection is deferred.

## Identity and invalidation

Namespace SHA256 covers the verified model and tokenizer artifact SHA256 mappings, ONNX Runtime version, CPU provider and `PREPROCESS_VERSION`. Current preprocessing explicitly identifies passage prefix, 512-token truncation, attention-mask mean pooling and L2 normalization. Any future change must bump that version. FP32 and INT8 have different model hashes. Moving unchanged verified artifacts does not require new embeddings. Replacing model files while the app is running is unsupported: restart or select a different folder to instantiate a verified encoder.

Per-record key hashes namespace + exact `passage: ` input text. Input punctuation/whitespace changes cause a miss; duplicate texts share one vector; title/order/type/year changes alone do not invalidate vectors, though the search index rebuilds. Another profile has its own records even for identical text. A record copied from another model namespace fails header validation. Query normalization and ranking are untouched.

## Format and failure behavior

Fixed 1608-byte binary record: 8-byte magic, 32-byte identity/text digest, 384 little-endian float32 values, 32-byte SHA256 checksum. Reader reads at most 1609 bytes and checks exact size, magic, identity, checksum, finite values and unit norm. No pickle, eval, np.load or executable deserialization. Cache files/direct cache directory symlinks are rejected on reads; writes replace the final entry instead of following it. This is not a security boundary against another process controlling the same user/profile or racing ancestor directories.

Write: unique tempfile in destination directory, flush + fsync file, atomic `os.replace`, cleanup temporary file. Concurrent writers can replace only with complete records for that key. This does not promise power-loss durability of directory metadata; missing records are safe to recompute. Disk full, read-only directory, corrupt/oversized/truncated record: use encoder and continue, cache errors only affect reuse. Cache does not authenticate against a malicious owner who can forge checksum/content. An interrupted process can leave an ignored `.tmp` file; no incomplete record is loaded. Cancellation between batches/writes remains in place.

The model is still verified and loaded on each process start. Cache avoids repeated passage inference, not model memory/load or query inference. Lexical index is rebuilt from live descriptions. No download is added.

## Linux measurements

Tool: `tools.qa.benchmark_story_cache`; each case runs in a fresh Python process, CPU FP32. Input: 120 distinct texts formed from 12 authorized external Russian TMDb descriptions plus synthetic numbered suffixes. This is a performance probe, not 120 independent titles and not a quality benchmark. OS filesystem cache and other machine activity are uncontrolled; numbers are single runs, not statistical estimates.

| Process | Model load | Index | Search including evidence | Total | Passage hits/misses | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|
| No disk cache | 2.393 s | 13.127 s | 128 ms | 15.671 s | — | 1129 MiB |
| Populate cache | 2.432 s | 12.721 s | 150 ms | 15.321 s | 0 / 120 | 1129 MiB |
| Restart | 1.995 s | 87 ms | 12 ms | 2.108 s | 120 / 0 | 869 MiB |
| Change one text | 1.865 s | 121 ms | 11 ms | 2.022 s | 119 / 1 | 869 MiB |

Restart index ~151× faster than no-cache index; end-to-end ~7.4×. Small populate-vs-baseline difference is measurement noise, not a claimed optimization. All vectors, scores, top-5 order and evidence hashes for baseline/populate/restart match exactly. Changed run writes one new full-description vector. Reports contain counts/times/hashes and synthetic keys, no source text.

Reproduction (existing optional dependencies/model; fresh temporary profile):

```bash
.venv/bin/python -m tools.qa.benchmark_story_cache --model-dir ../watchbane-models/multilingual-e5-small-portable --profile /tmp/NEW-watchbane-cache-probe --corpus ../watchbane-tmdb-smoke/corpus.json --count 120 --output /tmp/cache-probe.json
# Omit --corpus to use original synthetic demo stories; those timings are not directly comparable.
WATCHBANE_TEST_MODEL_DIR=../watchbane-models/multilingual-e5-small-portable QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_story_vector_cache.py tests/test_story_search.py tests/test_story_semantic.py tests/desktop/test_story_flow.py tests/candidate_modules tests/test_search_core.py tests/test_filter_popularity.py tests/test_tmdb_overrides.py -q
# 166 passed (includes real model equality and Qt flow).
```

Tests cover restart hits, only changed text recomputed, model/preprocessing/profile isolation, copied cross-model record, truncated/oversized/checksum/NaN corruption, atomic replace failure, concurrent writes, read-only cache, symlinks, cancellation, no query persistence and real E5 vector/rank/evidence equality. Existing candidates checks also pass.

## Windows manual acceptance (not executed here)

1. On a real Windows machine, prepare this source tree/requirements and verified FP32 model per SOURCE_PREVIEW.md. Use a disposable copied profile, never the production library. Launch `Start-Preview.cmd --profile C:\Watchbane-cache-test --model-dir C:\Watchbane-e5`.
2. Search in an existing local catalog; time first useful results and observe UI responsiveness. Close normally. Confirm `.vec` files under active profile's data folder `story_vectors_v1`, no query/synopsis text files.
3. Relaunch same command and query. Confirm same cards/order/excerpts and lower indexing time. Test tests/test_story_vector_cache.py plus real model tests under pytest for precise hit/miss verification.
4. In the disposable profile, change one synopsis through a supported import/edit flow; restart. Verify other vectors reused and one changed full-description vector added. Reordering titles alone must not re-encode descriptions.
5. With app closed, truncate one `.vec`, then restart: search succeeds and repairs it. Delete cache directory: search reconstructs it without changing watched/saved/hidden. Make cache read-only using Windows ACLs: search should still work, with no speedup.
6. Switch to another named profile: its cache must be separate. For model invalidation, use the mocked identity/preprocessing tests; do not substitute unverified model files or Windows-incompatible INT8. Run concurrency/atomic-write tests on NTFS and test Unicode paths.
7. Confirm saving, reopening saved items, title search and clean close while indexing. Record Python/Qt/ORT/CPU/RAM, timings and actual UI stalls. Linux results do not close Windows acceptance.

## Limits

Still loads FP32 (~470 MB weights) and ONNX session every restart; ~869 MiB measured peak on the cached probe. Cold model/GIL UI pause remains possible. No cache size quota/automatic pruning; one record is 1608 bytes plus filesystem overhead (many small files), so wide-catalog scale and cache retention policy require a separate step. Full Windows behavior, ACL/AV behavior and power-loss tests are unverified. No ranking improvement is claimed.

## Integration verification

Two actual Qt offscreen processes sharing a disposable 12-description SQLite profile completed search, save and reopening saved/search. First search 4.796 s on cache population versus 2.448 s after process restart; second in-session queries 339/110 ms. Model imports/loading still caused maximum heartbeat gaps ~1.02/1.05 s. Thus this increment improves repeated inference, not the previously recorded cold UI stall. Timings were taken on the same Linux environment with other tests potentially active.

Full suite after the increment: 1744 passed, 25 failed, 8 skipped (optional real-model tests run separately above). Failure IDs are identical to original preview's 25 failures; no new failures. `compileall candidates`, `git diff --check`, and incremental/full patch apply checks passed. No UI styling/layout changed in this increment. Original ZIP, preview patch and immutable V1 patch SHA256 values were rechecked unchanged.
