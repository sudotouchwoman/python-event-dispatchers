import logging
import queue
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from typing import Any, Callable, Iterable, Optional


class Stateful:
    def __init__(self, state: Any) -> None:
        self.state = state
        self.__lock = threading.Lock()

    def set_state(self, new_state: Any) -> None:
        with self.__lock:
            self.state = new_state


class DispatcherLoop:
    """
    Takes care of non-blocking dispatching of incoming requests.
    Runs an event loop in a separate thread. Calls are delegated
    to the provided `on_job` callback. Note that this callback will
    be triggered from different threads and thus should take
    care of sync/blocks.
    """

    def __init__(
        self,
        max_workers: Optional[int] = None,
        max_requests: int = 0,
        dispatcher: Callable[[Any], None] = lambda _: None,
        name: Optional[str] = None,
    ) -> None:
        self.__max_workers = max_workers
        self.__requests: "queue.Queue[Any]" = queue.Queue(maxsize=max_requests)
        self.dispatch = dispatcher
        self.__name = name
        self.__running = False
        self.__done = False

    def run(self) -> None:
        """Launches the dispatcher in a separate thread, thus
        this call will not block the caller thread

        Raises:
            RuntimeError: if called once already running
        """
        if self.__running:
            raise RuntimeError("already running dispatch")
        self.__running = True
        self.__loop = threading.Thread(
            name=self.__name if self.__name else "dispatcher",
            target=self.__run_dispatch_loop,
            daemon=True,
        )
        self.__loop.start()

    def stop(self) -> None:
        """Stops the loop by insertion of None item.
        This will not stop the loop immediately, rather
        stop the executor once it reaches the None item

        Raises:
            RuntimeError: if called on stopped dispatcher
        """
        if self.__done:
            raise RuntimeError("already stopped")
        self.__done = True
        self.__requests.put(None)

    def run_until_completed(self) -> None:
        self.__loop.join()

    def submit(self, job: Any, timeout: Optional[float] = None) -> None:
        """Delegates a task to the loop. Tries to put item into the queue

        Args:
            job (Any): payload to pass to the dispatcher
            timeout (Optional[float], optional): put timeout. Defaults to None.

        Raises:
            RuntimeError: if called once loop is already dead
        """
        if self.__done:
            raise RuntimeError("cannot submit to a dead loop")
        self.__requests.put(job, timeout=timeout, block=False)

    def __run_dispatch_loop(self) -> None:
        logging.debug(msg="starts loop")
        with ThreadPoolExecutor(max_workers=self.__max_workers) as executor:
            for _ in executor.map(
                self.dispatch, iter(self.__requests.get, None)
            ):
                self.__requests.task_done()
        logging.debug(msg="...loop done")


def dummy_producer(spawn_items: int = 10) -> Iterable[int]:
    logging.info(msg=f"I will produce {spawn_items} things and exit")
    for i in range(spawn_items):
        logging.info(msg=f"[{i}] Spawner: {i}")
        yield i
        sleep(random.random())
    logging.info(msg="...spawner done and exits")


class Consumer:
    def __init__(self) -> None:
        self.recieved = 0
        self.__lock = threading.Lock()

    def consume(self, thing: Any) -> None:
        # communicate with an external system...
        with self.__lock:
            logging.info(msg=f"[{self.recieved}] Consumer recieved: {thing}")
            self.recieved += 1
