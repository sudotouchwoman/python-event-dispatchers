from abc import ABC
import queue
from typing import Callable


class AgentAPI(ABC):
    """Agent APi acts as a narrowed
    interface for the actual agent

    This one is utilized by state machine
    to decide on state transitions. Machine
    triggers hooks to run io-bound tasks and
    predicates to decide on conditional statements
    (say, whether current location matches the
    requested one)
    """

    more_tasks: bool
    more_subtasks: bool
    more_exec_actions: bool
    more_path_actions: bool
    path_found: bool
    dest_reached: bool

    def next_subtask(self):
        # blocks until next subtask is decoded
        # and can be run
        pass

    def next_chunk(self):
        # blocks until next chunk is requested
        # SM will ping path_found property
        # after this one is called
        pass

    def listen_for_tasks(self):
        # start listening for tasks
        pass

    def check_dest_reached(self):
        # blocks to compare current location
        # with the requested one. should
        # update the `dist_reached` propery
        pass

    def send_move_action(self):
        # block until next command is executed
        # (say, agent communicated via network)
        pass

    def send_exec_action(self):
        # block until next move command is executed
        pass


class Submitter:
    def submit(self, hook: Callable[[], None]):
        # non-blocking method
        # puts hook into the queue
        pass


class Dispatcher:
    state_requests: queue.Queue
    io_requests: queue.Queue

    def __init__(self) -> None:
        self.state_requests = queue.Queue()
        self.io_requests = queue.Queue()

    def dispatch_next(self, event: Callable[[], None]):
        self.do_io_actions()
        event()

    def do_io_actions(self):
        self.io_requests.put(None)
        for r in iter(self.io_requests.get, None):
            r()

    def loop(self):
        # runs in separate thread, the sacred
        # request loop
        for r in iter(self.state_requests.get, None):
            self.dispatch_next(r)

    def stop(self):
        self.state_requests.put(None)
