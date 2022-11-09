import logging
from time import sleep
from typing import Any
from threaded.dispatcher import Consumer, DispatcherLoop, dummy_producer


def main() -> None:

    c = Consumer()

    def dispatch_func(request: Any):
        logging.info(msg=f"got request: {request}")
        sleep(5)
        c.consume(request)

    loop = DispatcherLoop(dispatcher=dispatch_func, name="request-loop")
    loop.run()

    for p in dummy_producer():
        loop.submit(p)


if __name__ == "__main__":
    main()
