import logging
import queue
from time import sleep
from typing import Any
from threaded.dispatcher import dummy_producer
from threaded.executor import WorkerPool, ConsumerWithQueue


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


def main() -> None:

    api = SimplePipeline()

    for p in dummy_producer():
        api.schedule(p)

    api.run_until_complete()


if __name__ == "__main__":
    main()
