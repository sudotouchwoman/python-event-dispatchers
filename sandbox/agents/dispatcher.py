import queue
import logging
from typing import Callable
from .types import Submitter


class Dispatcher:
    state_requests: queue.Queue
    io_requests: queue.Queue

    def __init__(self) -> None:
        self.state_requests = queue.Queue()
        self.io_requests = queue.Queue()
        self.log = logging.getLogger(__name__)

    def dispatch_next(self, event: Callable[[], None]):
        self.do_io_actions()
        event()

    def do_io_actions(self):
        self.io_requests.put(None)
        for r in iter(self.io_requests.get, None):
            self.io_requests.task_done()
            r()

    def loop(self):
        self.log.debug("loop start...")
        for r in iter(self.state_requests.get, None):
            self.state_requests.task_done()
            self.dispatch_next(r)
        self.log.debug("loop done...")

    def stop(self):
        self.state_requests.put(None)


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
