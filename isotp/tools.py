__all__ = ['Timer']
import time
from typing import Optional


class Timer:
    start_time: Optional[float]
    timeout: float

    def __init__(self, timeout: float):
        self.set_timeout(timeout)
        self.start_time = None

    def set_timeout(self, timeout: float) -> None:
        self.timeout = timeout

    def start(self, timeout=None) -> None:
        if timeout is not None:
            self.set_timeout(timeout)
        self.start_time = time.monotonic()

    def stop(self) -> None:
        self.start_time = None

    def elapsed(self) -> float:
        if self.start_time is not None:
            return time.monotonic() - self.start_time
        else:
            return 0

    def is_timed_out(self) -> bool:
        if self.is_stopped():
            return False
        else:
            return self.elapsed() > self.timeout or self.timeout == 0

    def is_stopped(self) -> bool:
        return self.start_time == None
