from contextlib import contextmanager


class WouldBlockError(RuntimeError):
    pass


@contextmanager
def nonblock_guard(lock, timeout: float = -1):
    if not lock.acquire(False, timeout=timeout):
        raise WouldBlockError
    try:
        yield lock
    finally:
        lock.release()
