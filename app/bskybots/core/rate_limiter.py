import time
from collections import deque

class RateLimiter:
    """
    Sliding-window limiter.
    - can(): prune & check capacity (NO consume)
    - take(): prune & consume a slot if available (returns True/False)
    - allow(): alias to take() for backward compat
    """
    def __init__(self, max_events, window_seconds):
        self.max_events = int(max_events)
        self.window = float(window_seconds)
        self.events = deque()

    def _prune(self):
        now = time.time()
        while self.events and now - self.events[0] > self.window:
            self.events.popleft()

    def can(self):
        self._prune()
        return len(self.events) < self.max_events

    def take(self):
        self._prune()
        if len(self.events) < self.max_events:
            self.events.append(time.time())
            return True
        return False

    def allow(self):  # backward-compatible alias
        return self.take()
