from abc import ABC
import logging
from typing import Callable


log = logging.getLogger(__name__)


class AgentStateAPI(ABC):
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
    more_subtasks: int
    more_exec_actions: int
    more_path_actions: int
    path_found: bool
    dest_reached: bool
    error_found: bool
    must_stop: bool


class AgentHooksAPI(ABC):
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

    def suspend(self):
        # stop processing events
        pass


class Submitter:
    def submit(self, hook: Callable[[], None]):
        # non-blocking method
        # puts hook into the queue
        pass
