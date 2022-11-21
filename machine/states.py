from enum import Enum, unique
import logging
import queue
from typing import Any, Callable, Dict, Optional
from statemachine import State, StateMachine
from statemachine.exceptions import TransitionNotAllowed


@unique
class States(str, Enum):
    IDLE = "idle"
    POWERSAVE = "powersave"
    GOT_TASK = "new_task"
    GOT_SUBTASK = "new_subtask"
    AWAIT_PATH = "awaits_path"
    MOVING = "moving"
    EXECUTING = "executing"
    ERROR = "error"


class AgentFSM(StateMachine):
    """Defines states and transitions for robot agent"""

    # state definitions
    idle = State(States.IDLE, initial=True)
    powersave = State(States.POWERSAVE)
    new_task = State(States.GOT_TASK)
    new_subtask = State(States.GOT_SUBTASK)
    awaits_path = State(States.AWAIT_PATH)
    moving = State(States.MOVING)
    executing = State(States.EXECUTING)
    error = State(States.EXECUTING)

    # transitions between states (in logical order)
    submit_task = idle.to(new_task)
    go_powersave = idle.to(powersave)
    go_idle = powersave.to(idle) | new_task.to(idle)
    submit_subtask = new_task.to(new_subtask)
    wait_for_path = new_subtask.to(awaits_path)
    ping_sleep = awaits_path.to.itself()
    got_path = awaits_path.to(moving)
    dest_not_reached = moving.to.itself()
    dest_reached = moving.to(new_subtask)
    do_action = new_subtask.to(executing)
    done_action = executing.to(new_subtask)
    done_subtask = new_subtask.to(new_task)
    done_task = new_task.to(idle)
    got_error = error.from_(
        awaits_path,
        moving,
        executing,
        new_subtask,
        new_task,
        idle,
    )
    recover = error.to(idle)

    def __init__(
        self,
        transition_hooks: Dict[str, Callable[[], None]] = {},
        state_hooks: Dict[States, Callable[[], None]] = {},
    ) -> None:
        """Creates state machine instance using given configuration
        of hooks. Hooks are expected to be zero-argument callables,
        and designed to be fired once machine enters corresponding state

        Args:
            transition_hooks (Dict[str, Callable[[], None]]): transition hooks
            state_hooks (Dict[str, Callable[[], None]]): per-state hooks
        """
        super().__init__()
        for trigger, hook in transition_hooks.items():
            setattr(self, f"on_{trigger}", hook)
        for state, hook in state_hooks.items():
            setattr(self, f"on_enter_{state.value}", hook)


class TransitionPromise:
    q: queue.Queue

    def __init__(self) -> None:
        self.q = queue.Queue(maxsize=1)

    def populate(self, value: Any = None):
        try:
            self.q.put_nowait(value)
        except queue.Full:
            pass

    def wait_for_it(self, timeout: Optional[float] = None) -> Any:
        try:
            v = self.q.get(timeout=timeout)
            self.q.task_done()
            return v
        except queue.Empty:
            return


class ActionDispatcher:
    actions: queue.Queue
    accepts: bool

    def __init__(self) -> None:
        self.accepts = False
        self.actions = queue.Queue()

    @property
    def submitter(self):
        """Returns a closure to pass actions to this dispatcher"""

        def r(action: Callable[[], Any]) -> TransitionPromise:
            if not self.accepts:
                raise RuntimeError("can only submit during transitions")
            p = TransitionPromise()
            self.actions.put_nowait((action, p))
            return p

        return r

    def perform_all(self):
        """Loops over submitted actions and performs them sequentially"""
        self.actions.put_nowait(None)
        logging.debug("Performs actions")
        for action, promise in iter(self.actions.get_nowait, None):
            self.actions.task_done()
            # block on action
            promise.populate(action())
        logging.debug("Actions done")


class TransitionDispatcher:
    __agent: Optional[AgentFSM]
    requests: queue.Queue

    def __init__(
        self,
        action_manager: ActionDispatcher,
        max_requests: int = 0,
    ) -> None:
        self.__agent = None
        self.requests = queue.Queue(maxsize=max_requests)
        self.action_manager = action_manager
        self.accepts_actions = True

    @property
    def agent(self) -> AgentFSM:
        if self.__agent is None:
            raise RuntimeError("Agent not set up")
        return self.__agent

    @agent.setter
    def agent(self, new_agent: AgentFSM):
        self.__agent = new_agent

    def stop(self):
        self.requests.put(None)

    def dispatch(self):
        logging.debug("Starts dispatcher")
        for request in iter(self.requests.get, None):
            self.requests.task_done()
            logging.debug(f"Got request: {request}")
            try:
                self.action_manager.accepts = True
                # perform the transition, that's when the hooks
                # are called
                getattr(self.agent, request)()
                logging.debug("Request done")
            except TransitionNotAllowed as e:
                # how do we want to propagate excetion/return
                # values to the caller?
                logging.warning(e)
            finally:
                self.action_manager.accepts = False
        # perform all actions collected during current transition
            self.action_manager.perform_all()

    @property
    def sender(self) -> Callable[[str], Any]:
        # creates submitter, a closure to send requests to the queue
        # submitter will wait for a spare slot to place its request
        def sub(event: str):
            if not hasattr(self.agent, event):
                raise ValueError(f"No such action: {event}")
            if not callable(getattr(self.agent, event)):
                raise ValueError(f"Must be a transition name: {event}")
            self.requests.put(event)

        return sub
