import queue
import logging
from typing import Callable

log = logging.getLogger(__name__)


class Dispatcher:
    state_requests: queue.Queue
    io_requests: queue.Queue

    def __init__(self) -> None:
        self.state_requests = queue.Queue()
        self.io_requests = queue.Queue()

    def dispatch_next(self, event: Callable[[], None]):
        self.do_io_actions()
        # log.debug("dispatches request")
        event()
        # log.debug("request done")

    def do_io_actions(self):
        self.io_requests.put(None)
        for r in iter(self.io_requests.get, None):
            self.io_requests.task_done()
            # log.debug("io-bound do")
            r()
            # log.debug("io-bound done")

    def loop(self):
        # runs in separate thread, the sacred
        # request loop
        for r in iter(self.state_requests.get, None):
            # log.debug("dispatching...")
            self.state_requests.task_done()
            self.dispatch_next(r)

    def stop(self):
        self.state_requests.put(None)
