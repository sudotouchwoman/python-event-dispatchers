from contextlib import contextmanager
import threading
from typing import Iterator


class WouldBlockError(RuntimeError):
    pass


@contextmanager
def nonblock_guard(lock, block: bool = False, timeout: float = -1):
    if not lock.acquire(block, timeout=timeout):
        raise WouldBlockError
    try:
        yield lock
    finally:
        lock.release()


class RWLock:
    def __init__(self) -> None:
        self.r_lock = threading.Lock()
        self.w_lock = threading.Lock()
        self.n_readers = 0

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        return self.w_lock.acquire(blocking, timeout)

    def release(self) -> None:
        self.w_lock.release()

    def r_acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        if not self.r_lock.acquire(blocking, timeout):
            return False
        self.n_readers += 1
        if self.n_readers == 1:
            self.w_lock.acquire()
        self.r_lock.release()
        return True

    def r_release(self) -> None:
        if self.n_readers < 0:
            raise RuntimeError("integrity broken")
        self.r_lock.acquire()
        self.n_readers -= 1
        if self.n_readers == 0:
            self.w_lock.release()
        self.r_lock.release()

    @contextmanager
    def read(
        self, blocking: bool = True, timeout: float = -1
    ) -> Iterator[None]:
        try:
            self.r_acquire(blocking, timeout)
            yield
        finally:
            self.r_release()
