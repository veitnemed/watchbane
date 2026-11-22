"""Optional per-process loopback budget: no query, identity, or request history."""
from threading import Lock
from time import monotonic_ns


_NS_SECOND = 1_000_000_000
_TOKEN_COST = 60 * _NS_SECOND


def local_rate_config(per_minute, burst):
    """None disables the budget. Bounded integer parameters only."""
    if per_minute is None and burst is None:
        return None
    if type(per_minute) is not int or not 1 <= per_minute <= 3600:
        raise ValueError("Local rate requires an integer from 1 to 3600 requests per minute.")
    if burst is None:
        burst = min(per_minute, 5)
    if type(burst) is not int or not 1 <= burst <= 60:
        raise ValueError("Local burst requires an integer from 1 to 60 requests.")
    return per_minute, burst


class LocalRateBudget:
    """Integer token bucket, refilled continuously using one monotonic tick."""

    def __init__(self, per_minute, burst, *, clock=None):
        if local_rate_config(per_minute, burst) != (per_minute, burst):
            raise ValueError("Expected bounded rate and burst configuration.")
        self._clock = monotonic_ns if clock is None else clock
        self._lock = Lock()
        self._per_minute = per_minute
        self._capacity = burst * _TOKEN_COST
        self._available = self._capacity
        self._last = self._clock()

    def retry_after(self):
        """Consume one token, or return an integer wait without consuming."""
        with self._lock:
            now = self._clock()
            if now > self._last:
                self._available = min(self._capacity, self._available + (now - self._last) * self._per_minute)
                self._last = now
            if self._available >= _TOKEN_COST:
                self._available -= _TOKEN_COST
                return None
            units_per_second = self._per_minute * _NS_SECOND
            return (_TOKEN_COST - self._available + units_per_second - 1) // units_per_second
