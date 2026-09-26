"""Thread-safe sliding-window rate limiter using Python standard library only."""
import threading
import time


class RateLimiter:
    """Sliding-window rate limiter that tracks requests per client IP.

    Attributes:
        limit: Maximum requests allowed per window.
        window: Window duration in seconds.
    """

    def __init__(self, limit: int = 60, window: int = 60):
        """Initialise the rate limiter.

        Args:
            limit: Maximum number of requests allowed per *window* seconds.
            window: Rolling window duration in seconds.
        """
        self.limit = limit
        self.window = window
        self._lock = threading.Lock()
        # Maps client_ip -> list of request timestamps (floats)
        self._buckets: dict[str, list[float]] = {}

    def is_allowed(self, client_ip: str) -> tuple[bool, int, int]:
        """Check whether *client_ip* may make another request.

        Args:
            client_ip: The remote address of the client.

        Returns:
            A 3-tuple of (allowed, remaining, reset_seconds) where:
            - allowed: True if the request is within limits.
            - remaining: How many requests the client may still make.
            - reset_seconds: Seconds until the oldest request expires.
        """
        now = time.monotonic()
        cutoff = now - self.window

        with self._lock:
            timestamps = self._buckets.get(client_ip, [])
            # Drop timestamps outside the rolling window
            timestamps = [ts for ts in timestamps if ts > cutoff]

            if len(timestamps) >= self.limit:
                # Calculate when the oldest request will fall out of the window
                reset = int(timestamps[0] - cutoff) + 1
                self._buckets[client_ip] = timestamps
                return False, 0, reset

            timestamps.append(now)
            self._buckets[client_ip] = timestamps
            remaining = self.limit - len(timestamps)
            # Oldest request determines reset time (or full window if no prior)
            reset = int(timestamps[0] - cutoff) + 1 if timestamps else self.window
            return True, remaining, reset

    def cleanup(self, max_entries: int = 10_000) -> None:
        """Remove expired buckets to prevent unbounded memory growth.

        Should be called periodically (e.g. every few minutes).  Holds the
        lock only briefly.

        Args:
            max_entries: If more than this many IPs are tracked, purge expired
                ones regardless.
        """
        now = time.monotonic()
        cutoff = now - self.window

        with self._lock:
            if len(self._buckets) < max_entries:
                return
            self._buckets = {
                ip: [ts for ts in tss if ts > cutoff]
                for ip, tss in self._buckets.items()
                if any(ts > cutoff for ts in tss)
            }
