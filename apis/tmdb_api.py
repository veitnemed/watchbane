"""Compatibility alias for the legacy TMDb API module."""

import sys

from apis.tmdb import client as _client

sys.modules[__name__] = _client
