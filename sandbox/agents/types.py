from abc import ABC
from typing import List
from dataclasses import dataclass
from enum import Enum, unique
from typing import Callable


@unique
class Locations(str, Enum):
    BASE = "base"
    LEVEL2 = "level 2"
    LEVEL3 = "level 3"


@dataclass
class SubTask:
    loc: Locations
    commands: List[str]


@dataclass
class Task:
    subtasks: List[SubTask]

    def next(self) -> SubTask:
        return self.subtasks.pop(0)

    @property
    def done(self) -> bool:
        return len(self.subtasks) == 0


class AgentState:
    """AgentState acts as a narrowed
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


class AgentAction(ABC):
    """
    Actions schedulable from the state machine.
    Implementations MUST ensure that the state is updated
    inside these hooks so that the machine ALWAYS
    accesses up-to-date state. These hooks can possibly take
    some time to complete the request (i.e., may be blocking) but only
    `send_exec_action`/`send_move_action`/`listen_for_tasks`
    are expected to block.
    """

    def done_task(self):
        """
        Called once current task is completed so that
        the agent could free resources or update some internal
        attributes.
        """

    def next_subtask(self):
        """
        Called when new task is recieved/a subtask have just been
        completed. Is expected to prepare (i.e., decode) next
        subtask.
        """

    def fetch_next_chunk(self):
        """
        Called when current location
        does not match the required once. Is expected
        not to block. Machine pings the state API
        until new chunk is recieved.
        """

    def listen_for_tasks(self):
        """
        Listen for incoming task requests. May block, but
        not forever so that error requests could be processed too.
        """

    def check_dest_reached(self):
        """
        Called for each subtask/chunk. Implementations MUST
        comply to an invariant: once this method completes,
        `dest_reached` property is up-to-date.
        """

    def send_move_action(self):
        """
        Called for each move action obtained from chunk.
        Implementations may block (e.g., for network communication
        or external confirmation). Should keep `more_move_actions`
        up-to-date.
        """

    def send_exec_action(self):
        """
        Called for each execution stage action in subtask.
        Implementations may block (e.g., for network communication
        or external confirmation). Should keep `more_exec_actions`
        up-to-date.
        """

    def suspend(self):
        """
        Unconditionally stop processing requests.
        Current request queue is still going to be
        processed.
        """


class Agent(AgentState, AgentAction):
    def submit(self, t: Task):
        """Submit given task to execution.
        Implementations may use queue or some other sort
        of synchronozation primitive for integrity and
        support for task queues.

        Args:
            t (Task): task to execute
        """


class Submitter:
    def submit(self, action: Callable[[], None]):
        """Non-blocking method. Schedules given action
        for execution somewhere.

        Args:
            action (Callable[[], None]): action to execute
        """
