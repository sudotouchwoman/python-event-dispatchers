from dataclasses import dataclass
import logging
import queue
import random
from time import sleep
from typing import Any, Callable, Tuple
from threaded.dispatcher import dummy_producer
from threaded.executor import WorkerPool, ConsumerWithQueue


class Job:
    name: str
    blocking: bool

    def should_reshedule(self, result: Any) -> bool:
        return False

    def start(self) -> Any:
        pass


@dataclass
class StatelessJob(Job):
    name: str
    blocking: bool = True
    should_reshedule: Callable[[Any], bool] = lambda _: False
    start: Callable[[], Any] = lambda: None


class Pipeline:
    def __init__(self) -> None:
        # one pool (with big number of workers) for io-bound, non-blocking
        # tasks and another pool with single worker for execution
        # (can only perform one task at once)
        self.shared_pool = WorkerPool(
            max_requests=1,
            max_workers=10,
            name="io-bound-pool",
        )
        self.atomic_pool = WorkerPool(
            max_workers=1,
            name="atomic-pool",
        )

        # pending -> execution_awaiting -> completed
        self.pending_jobs: queue.Queue[Job] = queue.Queue()
        self.resolved_jobs: queue.Queue[Tuple[Job, Any]] = queue.Queue()

        # these consumers connect the queues together
        # however, the idea was to submit callables, not primitive types
        # to achieve step skipping (e.g., one task might not
        # be waiting for io-bound
        # step or not occupy the execution slot, which is a critical area)
        self.pending_jobs_consumer = ConsumerWithQueue(
            self.pending_jobs,
            self.__submit_to_execution,
            name="job-queue",
        )
        self.resolved_jobs_consumer = ConsumerWithQueue(
            self.resolved_jobs,
            self.__resolve,
            name="job-resolved",
        )

    def __submit_to_execution(self, j: Job) -> Any:
        pool = self.atomic_pool if j.blocking else self.shared_pool
        pool.submit(lambda: (j, j.start()), self.resolved_jobs)
        logging.debug(msg=f"Submitted {j.name}")

    def __resolve(self, job_and_result: Tuple[Job, Any]) -> Any:
        job, result = job_and_result
        if not job.should_reshedule(result):
            return
        logging.debug(msg=f"Will reshedule: {job.name}")
        self.pending_jobs.put(job)

    def schedule(self, j: Job) -> None:
        self.pending_jobs.put(j)

    def run_until_complete(self) -> None:
        self.shared_pool.run_until_complete()
        self.atomic_pool.run_until_complete()
        self.pending_jobs_consumer.stop()
        self.resolved_jobs_consumer.stop()


class SimpleJob(Job):
    # this is an example of stateful job
    # some sort of a dispatcher can monitor the outcomes and
    # abort or reshedule
    def __init__(
        self, name: str, retries: int, blocking: bool = False
    ) -> None:
        self.name = name
        self.blocking = retries % 5 == 0
        self.tries, self.retries = 0, retries
        self.f = self.some_io_bound if blocking else self.some_atomic
        logging.info(msg=f"{name} {blocking=} {retries=}")

    def start(self) -> Any:
        # there, one may fit some additional logic
        # and possibly return blank nothing
        self.tries += 1
        logging.info(msg=f"Called {self.tries} times")
        # one can just omit the return value
        self.f(random.randint(0, 5))
        logging.info(msg=f"Needs {self.retries - self.tries} more calls")

    def some_io_bound(self, p: int) -> None:
        logging.info(msg=f"{self.name} IO-bound sleeps for {p}s")
        sleep(p)
        logging.info(msg=f"{self.name} IO-bound woke up")

    def some_atomic(self, p: int) -> None:
        logging.info(msg=f"{self.name} Atomic sleeps for {p}s")
        sleep(p)
        logging.info(msg=f"{self.name} Atomic woke up")

    def reshedule(self) -> bool:
        # some sort of a check performed
        # here, job just makes sure to run given number of times
        # one can store/modify the state in start function
        # e.g. make the job blocking
        return self.tries < self.retries

    def should_reshedule(self, _) -> bool:
        # will be given a call result as a parameter,
        # but we do not care about it here
        # because the state is stored in self.tries
        return self.reshedule()


def main() -> None:

    random.seed(42)

    api = Pipeline()

    for i, p in enumerate(dummy_producer()):
        api.schedule(SimpleJob(f"job-{i}", p))

    # in this example, jobs are produced from a fixed-size
    # generator and then can possibly re-schedule themselves into the loop
    # thus this prompt is put here, not that in a real
    # app, one is either likely to run this
    # in a =n infinite loop or kill without caring
    input("Press Enter to stop...\n")
    api.run_until_complete()


if __name__ == "__main__":
    main()
