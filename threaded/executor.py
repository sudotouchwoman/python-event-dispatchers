from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
import queue
import threading
from typing import Any, Callable, Optional


@dataclass
class JobWithCb:
    routine: Callable[[], Any]
    result: queue.Queue[Any]


class WorkerPool:
    def __init__(
        self,
        max_workers: Optional[int] = None,
        max_requests: int = 0,
        name: Optional[str] = None,
    ) -> None:
        self.__requests: "queue.Queue[Optional[JobWithCb]]" = queue.Queue(
            maxsize=max_requests
        )
        self.__name = name
        self.__workers = max_workers
        self.__loop = threading.Thread(
            name=self.__name if self.__name else "worker-pool",
            target=self.__dispatch_loop,
            daemon=True,
        )
        self.__loop.start()
        self.__done = False

    def submit(
        self,
        routine: Callable[[], Any],
        once_done: queue.Queue[Any],
        timeout: Optional[float] = None,
    ) -> None:
        if self.__done:
            raise RuntimeError("cannot submit to a dead loop")
        # propagates the callable and result channel to the worker pool
        # once done, the result of the future will be put into the given queue
        # caller might want to block on wait in that queue?
        self.__requests.put(
            JobWithCb(routine=routine, result=once_done),
            timeout=timeout,
            block=False,
        )
        logging.debug(msg="Submitted")

    def run_until_complete(self) -> None:
        # TODO: there is some sort of a bug
        # or I do miss something: when called, this method
        # does not really block on join!
        self.__done = True
        self.__requests.put(None)
        self.__loop.join()
        logging.info(msg="Completed")

    def __dispatch_loop(self) -> None:
        logging.debug(msg="starts loop")
        with ThreadPoolExecutor(max_workers=self.__workers) as executor:
            for job in iter(self.__requests.get, None):
                self.__requests.task_done()
                executor.submit(job.routine).add_done_callback(
                    lambda f: job.result.put_nowait(f.result())
                )
        logging.info(msg="...loop done")


class ConsumerWithQueue:
    def __init__(self) -> None:
        self.recieved = 0
        self.__lock = threading.Lock()
        self.__queue = queue.Queue()

        def routine():
            for thing in iter(self.__queue.get, None):
                self.consume(thing)
                self.__queue.task_done()

            logging.debug(msg=f"Recieved total of {self.recieved}")

        threading.Thread(
            daemon=False,
            name="consumer-with-queue",
            target=routine,
        ).start()

    @property
    def queue(self) -> queue.Queue[Any]:
        return self.__queue

    def consume(self, thing: Any) -> None:
        # communicate with an external system...
        with self.__lock:
            logging.info(msg=f"[{self.recieved}] Consuming: {thing}")
            self.recieved += 1

    def stop(self) -> None:
        self.__queue.put(None)
