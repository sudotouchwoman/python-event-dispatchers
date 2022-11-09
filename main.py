import logging
import random
from time import sleep
from typing import Any
from threaded.dispatcher import Consumer, DispatcherLoop, dummy_producer


def main() -> None:

    c = Consumer()

    def dispatch_func(request: Any):
        sleep_for = random.randint(0, 4)
        logging.info(
            msg=f"got request: {request}, going to sleep for {sleep_for}"
        )
        sleep(sleep_for)
        c.consume(request)

    loop = DispatcherLoop(dispatcher=dispatch_func, name="request-loop")
    loop.run()

    for p in dummy_producer():
        loop.submit(p)


if __name__ == "__main__":
    main()
