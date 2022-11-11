from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
import queue
import threading
from time import sleep
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
        # logging.debug(msg="Submitted")

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


def io_bound_task(task: Any) -> str:
    logging.debug(msg=f"IO-bound: {task}")
    sleep(10)
    logging.debug(msg=f"IO-bound done: {task}")
    return f"{task} (path found)"


def execute_task(task: Any) -> str:
    logging.debug(msg=f"Execution-bound: {task}")
    sleep(5)
    logging.debug(msg=f"Execution-bound done: {task}")
    return f"{task} (completed)"


class SimplePipeline:
    def __init__(self) -> None:
        # one pool (with big number of workers) for io-bound, non-blocking
        # tasks and another pool with single worker for execution
        # (can only perform one task at once)
        self.path_waiters_pool = WorkerPool(
            max_requests=1,
            max_workers=10,
            name="io-bound-pool",
        )
        self.execution_pool = WorkerPool(max_workers=1, name="exec-pool")

        # pending -> execution_awaiting -> completed
        self.pending_tasks: queue.Queue[Any] = queue.Queue()
        self.execution_awaiting_tasks: queue.Queue[Any] = queue.Queue()
        self.completed_tasks: queue.Queue[Any] = queue.Queue()

        # these consumers connect the queues together
        # however, the idea was to submit callables, not primitive types
        # to achieve step skipping (e.g., one task might not
        # be waiting for io-bound
        # step or not occupy the execution slot, which is a critical area)
        self.io_bound_consumer = ConsumerWithQueue(
            self.pending_tasks,
            self.__submit_to_path_waiters,
            name="io-bound-consumer",
        )
        self.execution_consumer = ConsumerWithQueue(
            self.execution_awaiting_tasks,
            self.__submit_to_execution,
            name="execution-bound-consumer",
        )
        self.final_consumer = ConsumerWithQueue(
            self.completed_tasks,
            lambda task: logging.info(msg=task),
            name="final-consumer",
        )

    def __submit_to_execution(self, task: Any) -> Any:
        self.execution_pool.submit(
            lambda: execute_task(task), self.completed_tasks
        )

    def __submit_to_path_waiters(self, task: Any) -> Any:
        self.path_waiters_pool.submit(
            lambda: io_bound_task(task), self.execution_awaiting_tasks
        )

    def schedule(self, task: Any) -> None:
        self.pending_tasks.put(task)

    def run_until_complete(self) -> None:
        self.path_waiters_pool.run_until_complete()
        self.io_bound_consumer.stop()
        self.execution_pool.run_until_complete()
        self.execution_consumer.stop()
        self.final_consumer.stop()
