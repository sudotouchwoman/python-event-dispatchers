import queue
import logging
from typing import Callable, Iterable, Tuple
from .types import Submitter

# Actually, both requests and actions have the
# same signature for now
Request = Action = Callable[[], None]


class Dispatcher:
    state_requests: queue.Queue
    io_requests: queue.Queue
    __done: bool

    def __init__(self) -> None:
        self.state_requests = queue.Queue()
        self.io_requests = queue.Queue()
        self.__done = False
        self.log = logging.getLogger(__name__)

    def __io_actions(self) -> Iterable[Action]:
        """
        Returns iterator over pending io tasks

        Returns:
            Iterable[Action]: callbacks for io actions
        """
        self.io_requests.put(None)
        for r in iter(self.io_requests.get, None):
            self.io_requests.task_done()
            yield r

    def loop(self):
        """
        Runs the request/action loop locally (useful for
        things like testing)
        """
        self.log.debug("loop start...")

        def requests():
            while not self.__done:
                yield self.request_and_actions()

        for tr, actions in requests():
            for a in actions:
                a()
            tr()
        self.log.debug("loop done...")

    def request_and_actions(self) -> Tuple[Request, Iterable[Action]]:
        r = self.state_requests.get()
        self.state_requests.task_done()
        return r, self.__io_actions()

    def stop(self):
        self.__done = True


class AgentLoop(Dispatcher):
    class LoopSumbitter(Submitter):
        __q: queue.Queue

        def __init__(self, q: queue.Queue) -> None:
            self.__q = q

        def submit(self, hook: Callable[[], None]):
            self.__q.put(hook)

    def __init__(self) -> None:
        super().__init__()
        self.state_submitter = self.LoopSumbitter(self.state_requests)
        self.io_submitter = self.LoopSumbitter(self.io_requests)
