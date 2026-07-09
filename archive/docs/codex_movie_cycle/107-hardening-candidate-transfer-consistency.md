# 107 Hardening Candidate Transfer Consistency

Date: 2026-07-08

Weak spots found:
- Candidate/add meta payload allowlists preserved TV fields but omitted movie-specific `media_type`, `release_date`, and `runtime`.
- Watched record could keep movie type while meta lost movie-specific fields.

Fixed:
- Added movie fields to add/candidate meta payload allowlists.
- Added regression coverage in metadata tests.

Checks:
- `py -m compileall dataset\meta tests\test_metadata_gui.py` passed.
- `py -m pytest tests\test_metadata_gui.py` passed: `7 passed`.
