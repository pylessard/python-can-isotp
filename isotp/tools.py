__all__ = ['Timer']
import time
from typing import Optional


class Timer:
    start_time: Optional[int]
    timeout: int

    def __init__(self, timeout: float):
        self.set_timeout(timeout)
        self.start_time = None

    def set_timeout(self, timeout: float) -> None:
        self.timeout = int(timeout * 1e9)

    def start(self, timeout=None) -> None:
        if timeout is not None:
            self.set_timeout(timeout)
        self.start_time = time.monotonic_ns()

    def stop(self) -> None:
        self.start_time = None

    def elapsed(self) -> float:
        if self.start_time is not None:
            return float(time.monotonic_ns() - self.start_time) / 1.0e9
        else:
            return 0

    def elapsed_ns(self) -> int:
        if self.start_time is not None:
            return time.monotonic_ns() - self.start_time
        else:
            return 0

    def remaining_ns(self) -> int:
        if self.is_stopped():
            return 0
        return max(0, self.timeout - self.elapsed_ns())

    def remaining(self) -> float:
        return float(self.remaining_ns()) / 1e9

    def is_timed_out(self) -> bool:
        if self.is_stopped():
            return False
        else:
            return self.elapsed_ns() > self.timeout or self.timeout == 0

    def is_stopped(self) -> bool:
        return self.start_time == None
