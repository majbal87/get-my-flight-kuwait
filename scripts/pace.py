"""Steady pacing shared by the source modules: a minimum gap between request starts, plus a little jitter."""
import random, threading, time


class Pace:
    def __init__(self, gap):
        self.gap, self.next, self.lock = gap, 0.0, threading.Lock()

    def wait(self):
        """Call before each request. Spreads requests from all threads gap..1.3*gap seconds apart."""
        with self.lock:
            start = max(time.time(), self.next)
            self.next = start + self.gap * random.uniform(1, 1.3)
        time.sleep(max(0.0, start - time.time()))

    def hold(self, secs):
        """Nobody starts a request for the next `secs` seconds (after a block / Retry-After)."""
        with self.lock:
            self.next = max(self.next, time.time() + secs)


def retry_after(r):
    """Seconds from a Retry-After header (numbers only), else None."""
    v = (r.headers or {}).get("retry-after", "")
    return int(v) if str(v).strip().isdigit() else None
