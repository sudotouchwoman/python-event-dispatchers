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
        self.__name = name if name else "worker-pool"
        self.__workers = max_workers
        self.__loop = threading.Thread(
            name=self.__name,
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
        logging.info(msg=f"{self.__name} exited")

    def __dispatch_loop(self) -> None:
        logging.debug(msg="starts loop")
        with ThreadPoolExecutor(
            max_workers=self.__workers,
            thread_name_prefix=self.__name,
        ) as executor:
            for job in iter(self.__requests.get, None):
                self.__requests.task_done()
                executor.submit(job.routine).add_done_callback(
                    lambda f: job.result.put_nowait(f.result())
                )
        logging.info(msg=f"...{self.__name} done")


class ConsumerWithQueue:
    def __init__(
        self,
        input_channel: queue.Queue[Any],
        consumer_func: Callable[[Any], None],
        name: str = "consumer-with-queue",
    ) -> None:
        self.recieved = []
        self.__queue = input_channel
        self.consume_task = consumer_func
        self.__lock = threading.Lock()

        def routine():
            for task in iter(self.__queue.get, None):
                self.consume_task(task)
                with self.__lock:
                    self.recieved += [task]
                self.__queue.task_done()

            logging.debug(msg=f"Recieved in total: {len(self.recieved)}")

        threading.Thread(
            daemon=False,
            name=name,
            target=routine,
        ).start()

    @property
    def queue(self) -> queue.Queue[Any]:
        return self.__queue

    def stop(self) -> None:
        self.__queue.put(None)
