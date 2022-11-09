import logging
import random
from time import sleep
from typing import Any
from threaded.dispatcher import dummy_producer
from threaded.executor import WorkerPool, ConsumerWithQueue


def main() -> None:

    c = ConsumerWithQueue()

    def dispatch_func(p: Any) -> Any:
        sleep_for = random.randint(0, 10)
        sleep_for = 5
        logging.info(msg=f"Sleeper: {p}, going to sleep for {sleep_for}")
        sleep(sleep_for)
        return p + f" (slept for {sleep_for})"

    # loop = WorkerPool(max_workers=3)
    loop = WorkerPool(max_requests=1, max_workers=2)

    for p in dummy_producer():
        loop.submit(lambda p=p: dispatch_func(p), c.queue)

    # why calling this has no effect?
    # loop thread is not joined...
    loop.run_until_complete()
    c.stop()


if __name__ == "__main__":
    main()
