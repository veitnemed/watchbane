# Onboarding Pool Scenario Report

- Mode: mock
- Generated: 2026-07-08T22:46:13.590258+00:00
- TMDb credentials present: True
- Target: 120

## baseline_quota_fix / en-tv-new-dark

- Profile: `{"media_preference": "tv", "release_preference": "new", "vibe_preference": "dark", "origin_preference": null, "ui_language": "en"}`
- Created/pool: 120 / 120
- Quota integrity: True
- API requests: 33
- Elapsed ms: 4015.0
- Planned media: `{'movie': 36, 'tv': 84}`
- Actual media: `{'tv': 84, 'movie': 36}`
- Planned origin: `{'any': 120}`
- Actual origin: `{'any': 120}`
- Source contributions: `{'focused': 63, 'fallback': 57}`
- Fallbacks: `{'base': 63, 'relax_origin': 31, 'relax_genres': 14, 'relax_votes_mid': 7, 'relax_votes_low': 4, 'relax_era': 1}`
- Future rejected: 0
- Quota mismatch rejected: 0
- Duplicate rejected: 0
- Top languages: `{'en': 120}`
- Warnings: `[]`

## baseline_quota_fix / ru-balanced

- Profile: `{"media_preference": "both", "release_preference": "mixed", "vibe_preference": "mixed", "origin_preference": "mixed", "ui_language": "ru"}`
- Created/pool: 120 / 120
- Quota integrity: True
- API requests: 81
- Elapsed ms: 9515.6
- Planned media: `{'movie': 60, 'tv': 60}`
- Actual media: `{'tv': 60, 'movie': 60}`
- Planned origin: `{'domestic': 60, 'foreign': 60}`
- Actual origin: `{'domestic': 60, 'foreign': 60}`
- Source contributions: `{'focused': 65, 'fallback': 55}`
- Fallbacks: `{'base': 65, 'relax_genres': 37, 'relax_votes_mid': 17, 'relax_votes_low': 1}`
- Future rejected: 0
- Quota mismatch rejected: 0
- Duplicate rejected: 0
- Top languages: `{'ru': 59, 'en': 31, 'ko': 7, 'ja': 7, 'fr': 5, 'es': 5, 'de': 3, 'it': 3}`
- Warnings: `[]`

## baseline_quota_fix / ru-domestic-movie-classic-light

- Profile: `{"media_preference": "movie", "release_preference": "classic", "vibe_preference": "light", "origin_preference": "domestic", "ui_language": "ru"}`
- Created/pool: 120 / 120
- Quota integrity: True
- API requests: 57
- Elapsed ms: 6690.0
- Planned media: `{'movie': 84, 'tv': 36}`
- Actual media: `{'movie': 84, 'tv': 36}`
- Planned origin: `{'domestic': 84, 'foreign': 36}`
- Actual origin: `{'domestic': 84, 'foreign': 36}`
- Source contributions: `{'focused': 67, 'fallback': 53}`
- Fallbacks: `{'base': 67, 'relax_genres': 34, 'relax_votes_mid': 12, 'relax_votes_low': 5, 'relax_era': 2}`
- Future rejected: 0
- Quota mismatch rejected: 0
- Duplicate rejected: 0
- Top languages: `{'ru': 77, 'en': 25, 'ko': 4, 'ja': 4, 'fr': 3, 'es': 3, 'de': 2, 'it': 2}`
- Warnings: `[]`

## broad_top_seed / en-tv-new-dark

- Profile: `{"media_preference": "tv", "release_preference": "new", "vibe_preference": "dark", "origin_preference": null, "ui_language": "en"}`
- Created/pool: 120 / 120
- Quota integrity: True
- API requests: 33
- Elapsed ms: 4110.6
- Planned media: `{'movie': 36, 'tv': 84}`
- Actual media: `{'tv': 84, 'movie': 36}`
- Planned origin: `{'any': 120}`
- Actual origin: `{'any': 120}`
- Source contributions: `{'quality_seed': 63, 'focused': 31, 'fallback': 26}`
- Fallbacks: `{'quality_seed': 63, 'base': 31, 'relax_origin': 14, 'relax_genres': 7, 'relax_votes_mid': 4, 'relax_votes_low': 1}`
- Future rejected: 0
- Quota mismatch rejected: 0
- Duplicate rejected: 0
- Top languages: `{'en': 120}`
- Warnings: `[]`

## broad_top_seed / ru-balanced

- Profile: `{"media_preference": "both", "release_preference": "mixed", "vibe_preference": "mixed", "origin_preference": "mixed", "ui_language": "ru"}`
- Created/pool: 120 / 120
- Quota integrity: True
- API requests: 101
- Elapsed ms: 9782.3
- Planned media: `{'movie': 60, 'tv': 60}`
- Actual media: `{'tv': 60, 'movie': 60}`
- Planned origin: `{'domestic': 60, 'foreign': 60}`
- Actual origin: `{'domestic': 60, 'foreign': 60}`
- Source contributions: `{'origin_top_seed': 30, 'quality_seed': 17, 'focused': 47, 'fallback': 26}`
- Fallbacks: `{'origin_top_seed': 30, 'quality_seed': 17, 'base': 47, 'relax_genres': 21, 'relax_votes_mid': 5}`
- Future rejected: 0
- Quota mismatch rejected: 400
- Duplicate rejected: 0
- Top languages: `{'en': 60, 'ru': 30, 'ko': 7, 'ja': 7, 'fr': 5, 'es': 5, 'de': 3, 'it': 3}`
- Warnings: `[]`

## broad_top_seed / ru-domestic-movie-classic-light

- Profile: `{"media_preference": "movie", "release_preference": "classic", "vibe_preference": "light", "origin_preference": "domestic", "ui_language": "ru"}`
- Created/pool: 120 / 120
- Quota integrity: True
- API requests: 73
- Elapsed ms: 7086.7
- Planned media: `{'movie': 84, 'tv': 36}`
- Actual media: `{'movie': 84, 'tv': 36}`
- Planned origin: `{'domestic': 84, 'foreign': 36}`
- Actual origin: `{'domestic': 84, 'foreign': 36}`
- Source contributions: `{'origin_top_seed': 44, 'quality_seed': 11, 'focused': 40, 'fallback': 25}`
- Fallbacks: `{'origin_top_seed': 44, 'quality_seed': 11, 'base': 40, 'relax_genres': 18, 'relax_votes_mid': 5, 'relax_votes_low': 2}`
- Future rejected: 0
- Quota mismatch rejected: 320
- Duplicate rejected: 0
- Top languages: `{'en': 64, 'ru': 38, 'ko': 4, 'ja': 4, 'fr': 3, 'es': 3, 'de': 2, 'it': 2}`
- Warnings: `[]`

## focused_first / en-tv-new-dark

- Profile: `{"media_preference": "tv", "release_preference": "new", "vibe_preference": "dark", "origin_preference": null, "ui_language": "en"}`
- Created/pool: 120 / 120
- Quota integrity: True
- API requests: 33
- Elapsed ms: 4035.6
- Planned media: `{'movie': 36, 'tv': 84}`
- Actual media: `{'tv': 84, 'movie': 36}`
- Planned origin: `{'any': 120}`
- Actual origin: `{'any': 120}`
- Source contributions: `{'focused': 63, 'quality_seed': 31, 'fallback': 26}`
- Fallbacks: `{'base': 63, 'quality_seed': 31, 'relax_origin': 14, 'relax_genres': 7, 'relax_votes_mid': 4, 'relax_votes_low': 1}`
- Future rejected: 0
- Quota mismatch rejected: 0
- Duplicate rejected: 0
- Top languages: `{'en': 120}`
- Warnings: `[]`

## focused_first / ru-balanced

- Profile: `{"media_preference": "both", "release_preference": "mixed", "vibe_preference": "mixed", "origin_preference": "mixed", "ui_language": "ru"}`
- Created/pool: 120 / 120
- Quota integrity: True
- API requests: 100
- Elapsed ms: 9597.9
- Planned media: `{'movie': 60, 'tv': 60}`
- Actual media: `{'tv': 60, 'movie': 60}`
- Planned origin: `{'domestic': 60, 'foreign': 60}`
- Actual origin: `{'domestic': 60, 'foreign': 60}`
- Source contributions: `{'focused': 65, 'origin_top_seed': 17, 'quality_seed': 12, 'fallback': 26}`
- Fallbacks: `{'base': 65, 'origin_top_seed': 17, 'quality_seed': 12, 'relax_genres': 21, 'relax_votes_mid': 5}`
- Future rejected: 0
- Quota mismatch rejected: 380
- Duplicate rejected: 0
- Top languages: `{'en': 47, 'ru': 43, 'ko': 7, 'ja': 7, 'fr': 5, 'es': 5, 'de': 3, 'it': 3}`
- Warnings: `[]`

## focused_first / ru-domestic-movie-classic-light

- Profile: `{"media_preference": "movie", "release_preference": "classic", "vibe_preference": "light", "origin_preference": "domestic", "ui_language": "ru"}`
- Created/pool: 120 / 120
- Quota integrity: True
- API requests: 70
- Elapsed ms: 7030.9
- Planned media: `{'movie': 84, 'tv': 36}`
- Actual media: `{'movie': 84, 'tv': 36}`
- Planned origin: `{'domestic': 84, 'foreign': 36}`
- Actual origin: `{'domestic': 84, 'foreign': 36}`
- Source contributions: `{'focused': 67, 'origin_top_seed': 23, 'quality_seed': 5, 'fallback': 25}`
- Fallbacks: `{'base': 67, 'origin_top_seed': 23, 'quality_seed': 5, 'relax_genres': 18, 'relax_votes_mid': 5, 'relax_votes_low': 2}`
- Future rejected: 0
- Quota mismatch rejected: 260
- Duplicate rejected: 0
- Top languages: `{'ru': 59, 'en': 43, 'ko': 4, 'ja': 4, 'fr': 3, 'es': 3, 'de': 2, 'it': 2}`
- Warnings: `[]`

## hybrid_quality_focused / en-tv-new-dark

- Profile: `{"media_preference": "tv", "release_preference": "new", "vibe_preference": "dark", "origin_preference": null, "ui_language": "en"}`
- Created/pool: 120 / 120
- Quota integrity: True
- API requests: 33
- Elapsed ms: 4078.2
- Planned media: `{'movie': 36, 'tv': 84}`
- Actual media: `{'tv': 84, 'movie': 36}`
- Planned origin: `{'any': 120}`
- Actual origin: `{'any': 120}`
- Source contributions: `{'focused': 63, 'quality_seed': 31, 'fallback': 26}`
- Fallbacks: `{'base': 63, 'quality_seed': 31, 'relax_origin': 14, 'relax_genres': 7, 'relax_votes_mid': 4, 'relax_votes_low': 1}`
- Future rejected: 0
- Quota mismatch rejected: 0
- Duplicate rejected: 0
- Top languages: `{'en': 120}`
- Warnings: `[]`

## hybrid_quality_focused / ru-balanced

- Profile: `{"media_preference": "both", "release_preference": "mixed", "vibe_preference": "mixed", "origin_preference": "mixed", "ui_language": "ru"}`
- Created/pool: 120 / 120
- Quota integrity: True
- API requests: 101
- Elapsed ms: 9690.3
- Planned media: `{'movie': 60, 'tv': 60}`
- Actual media: `{'tv': 60, 'movie': 60}`
- Planned origin: `{'domestic': 60, 'foreign': 60}`
- Actual origin: `{'domestic': 60, 'foreign': 60}`
- Source contributions: `{'origin_top_seed': 30, 'quality_seed': 17, 'focused': 47, 'fallback': 26}`
- Fallbacks: `{'origin_top_seed': 30, 'quality_seed': 17, 'base': 47, 'relax_genres': 21, 'relax_votes_mid': 5}`
- Future rejected: 0
- Quota mismatch rejected: 400
- Duplicate rejected: 0
- Top languages: `{'en': 60, 'ru': 30, 'ko': 7, 'ja': 7, 'fr': 5, 'es': 5, 'de': 3, 'it': 3}`
- Warnings: `[]`

## hybrid_quality_focused / ru-domestic-movie-classic-light

- Profile: `{"media_preference": "movie", "release_preference": "classic", "vibe_preference": "light", "origin_preference": "domestic", "ui_language": "ru"}`
- Created/pool: 120 / 120
- Quota integrity: True
- API requests: 70
- Elapsed ms: 6850.9
- Planned media: `{'movie': 84, 'tv': 36}`
- Actual media: `{'movie': 84, 'tv': 36}`
- Planned origin: `{'domestic': 84, 'foreign': 36}`
- Actual origin: `{'domestic': 84, 'foreign': 36}`
- Source contributions: `{'focused': 67, 'origin_top_seed': 23, 'quality_seed': 5, 'fallback': 25}`
- Fallbacks: `{'base': 67, 'origin_top_seed': 23, 'quality_seed': 5, 'relax_genres': 18, 'relax_votes_mid': 5, 'relax_votes_low': 2}`
- Future rejected: 0
- Quota mismatch rejected: 260
- Duplicate rejected: 0
- Top languages: `{'ru': 59, 'en': 43, 'ko': 4, 'ja': 4, 'fr': 3, 'es': 3, 'de': 2, 'it': 2}`
- Warnings: `[]`

## strict_underfill / en-tv-new-dark

- Profile: `{"media_preference": "tv", "release_preference": "new", "vibe_preference": "dark", "origin_preference": null, "ui_language": "en"}`
- Created/pool: 63 / 63
- Quota integrity: False
- API requests: 8
- Elapsed ms: 970.3
- Planned media: `{'movie': 36, 'tv': 84}`
- Actual media: `{'tv': 43, 'movie': 20}`
- Planned origin: `{'any': 120}`
- Actual origin: `{'any': 63}`
- Source contributions: `{'focused': 63}`
- Fallbacks: `{'base': 63}`
- Future rejected: 0
- Quota mismatch rejected: 0
- Duplicate rejected: 0
- Top languages: `{'en': 63}`
- Warnings: `['Starter pool underfilled: created 63 of 120.', 'Only 63 candidates collected; the pool can be topped up later.', 'Media quota underfilled: movie planned 36, actual 20.', 'Media quota underfilled: tv planned 84, actual 43.']`

## strict_underfill / ru-balanced

- Profile: `{"media_preference": "both", "release_preference": "mixed", "vibe_preference": "mixed", "origin_preference": "mixed", "ui_language": "ru"}`
- Created/pool: 65 / 65
- Quota integrity: False
- API requests: 32
- Elapsed ms: 3602.5
- Planned media: `{'movie': 60, 'tv': 60}`
- Actual media: `{'tv': 32, 'movie': 33}`
- Planned origin: `{'domestic': 60, 'foreign': 60}`
- Actual origin: `{'domestic': 30, 'foreign': 35}`
- Source contributions: `{'focused': 65}`
- Fallbacks: `{'base': 65}`
- Future rejected: 0
- Quota mismatch rejected: 0
- Duplicate rejected: 0
- Top languages: `{'ru': 30, 'en': 17, 'ko': 4, 'ja': 4, 'fr': 3, 'es': 3, 'de': 2, 'it': 2}`
- Warnings: `['Starter pool underfilled: created 65 of 120.', 'Only 65 candidates collected; the pool can be topped up later.', 'Media quota underfilled: movie planned 60, actual 33.', 'Media quota underfilled: tv planned 60, actual 32.', 'Origin quota underfilled: domestic planned 60, actual 30.', 'Origin quota underfilled: foreign planned 60, actual 35.']`

## strict_underfill / ru-domestic-movie-classic-light

- Profile: `{"media_preference": "movie", "release_preference": "classic", "vibe_preference": "light", "origin_preference": "domestic", "ui_language": "ru"}`
- Created/pool: 67 / 67
- Quota integrity: False
- API requests: 23
- Elapsed ms: 2729.8
- Planned media: `{'movie': 84, 'tv': 36}`
- Actual media: `{'movie': 47, 'tv': 20}`
- Planned origin: `{'domestic': 84, 'foreign': 36}`
- Actual origin: `{'domestic': 44, 'foreign': 23}`
- Source contributions: `{'focused': 67}`
- Fallbacks: `{'base': 67}`
- Future rejected: 0
- Quota mismatch rejected: 0
- Duplicate rejected: 0
- Top languages: `{'ru': 44, 'en': 11, 'ko': 3, 'ja': 3, 'fr': 2, 'es': 2, 'de': 1, 'it': 1}`
- Warnings: `['Starter pool underfilled: created 67 of 120.', 'Only 67 candidates collected; the pool can be topped up later.', 'Media quota underfilled: movie planned 84, actual 47.', 'Media quota underfilled: tv planned 36, actual 20.', 'Origin quota underfilled: domestic planned 84, actual 44.', 'Origin quota underfilled: foreign planned 36, actual 23.']`
