# Onboarding Pool Scenario Report

- Mode: live
- Generated: 2026-07-08T21:19:34.973209+00:00
- TMDb credentials present: True
- Target: 120

## en-tv-new-dark

- Profile: `{"media_preference": "tv", "release_preference": "new", "vibe_preference": "dark", "origin_preference": null, "ui_language": "en"}`
- Created/pool: 120 / 120
- API requests: 33
- Elapsed ms: 32224.5
- Planned media: `{'movie': 36, 'tv': 84}`
- Actual media: `{'tv': 84, 'movie': 36}`
- Planned origin: `{'any': 120}`
- Actual origin: `{'any': 120}`
- Fallbacks: `{'base': 120}`
- Future rejected: 0
- Warnings: `[]`

## ru-balanced

- Profile: `{"media_preference": "both", "release_preference": "mixed", "vibe_preference": "mixed", "origin_preference": "mixed", "ui_language": "ru"}`
- Created/pool: 99 / 99
- API requests: 180
- Elapsed ms: 125978.0
- Planned media: `{'movie': 60, 'tv': 60}`
- Actual media: `{'tv': 50, 'movie': 49}`
- Planned origin: `{'domestic': 60, 'foreign': 60}`
- Actual origin: `{'foreign': 60, 'domestic': 39}`
- Fallbacks: `{'base': 54, 'relax_genres': 4, 'relax_votes_mid': 1, 'relax_votes_low': 6, 'relax_era': 26, 'popular': 8}`
- Future rejected: 0
- Warnings: `['Starter pool underfilled: created 99 of 120.', 'Media quota underfilled: movie planned 60, actual 49.', 'Media quota underfilled: tv planned 60, actual 50.', 'Origin quota underfilled: domestic planned 60, actual 39.']`

## ru-domestic-movie-classic-light

- Profile: `{"media_preference": "movie", "release_preference": "classic", "vibe_preference": "light", "origin_preference": "domestic", "ui_language": "ru"}`
- Created/pool: 90 / 90
- API requests: 180
- Elapsed ms: 83695.9
- Planned media: `{'movie': 84, 'tv': 36}`
- Actual media: `{'movie': 62, 'tv': 28}`
- Planned origin: `{'domestic': 84, 'foreign': 36}`
- Actual origin: `{'domestic': 54, 'foreign': 36}`
- Fallbacks: `{'base': 31, 'relax_genres': 6, 'relax_votes_low': 4, 'relax_era': 44, 'popular': 5}`
- Future rejected: 0
- Warnings: `['Starter pool underfilled: created 90 of 120.', 'Media quota underfilled: movie planned 84, actual 62.', 'Media quota underfilled: tv planned 36, actual 28.', 'Origin quota underfilled: domestic planned 84, actual 54.']`
