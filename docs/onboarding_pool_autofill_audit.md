# Onboarding Pool Autofill Audit

Date: 2026-07-08

## Findings

- Plan generation already produced correct target quotas for media, release, vibe and RU origin.
- Execution could overfill a bucket by a full TMDb page because accepted results were capped only by total target, not by the current bucket quota.
- `relax_origin` removed RU origin filters for domestic/foreign buckets, which allowed silent replacement of domestic/foreign intent.
- Discover requests did not send `primary_release_date.lte` / `first_air_date.lte`, and acceptance did not reject future titles.
- Result payloads did not expose planned vs actual media/origin counts, so the UI could only say how many records were created.

## Fixed Contract

- Media quota is a hard parent quota: no movie/TV overfill is used to compensate for scarcity in the other media type.
- RU origin quota is hard by country bucket: domestic remains `with_origin_country=RU`; foreign remains the configured language bucket.
- Domestic original language is preferred, then relaxed only on late fallback while keeping `with_origin_country=RU`.
- Future/unreleased titles are rejected and counted.
- Underfill is allowed only with explicit warnings and actual/planned counts.

## Main Code Paths

- `candidates/onboarding/autofill.py`
- `candidates/service.py`
- `desktop/onboarding/wizard.py`
- `desktop/onboarding/worker.py`
- `scripts/run_onboarding_pool_rebuild.py`
