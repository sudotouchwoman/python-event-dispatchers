from enum import Enum, unique
import logging
from time import sleep
from typing import Callable
from statemachine import State, StateMachine

from .types import AgentHooksAPI, AgentStateAPI, Submitter

log = logging.getLogger(__name__)


# FA initiates io-bound tasks, but does not block
# inside states
# once entered a state, FA decides on a new transition
# once transition is complete, runner blocks on io-bound tasks
# after all io-bound tasks are completed, a new state is picked from
# the queue


@unique
class States(str, Enum):
    INITIAL = "off"
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
    initial = State(States.INITIAL, initial=True)
    idle = State(States.IDLE)
    powersave = State(States.POWERSAVE)
    new_task = State(States.GOT_TASK)
    new_subtask = State(States.GOT_SUBTASK)
    awaits_path = State(States.AWAIT_PATH)
    moving = State(States.MOVING)
    executing = State(States.EXECUTING)
    error = State(States.EXECUTING)

    # transitions between states (in logical order)
    start = initial.to(idle)
    stop = idle.to(initial)
    ping_idle = idle.to.itself()
    submit_task = idle.to(new_task)
    go_powersave = idle.to(powersave)
    go_idle = powersave.to(idle) | new_task.to(idle)
    submit_subtask = new_task.to(new_subtask)
    wait_for_path = new_subtask.to(awaits_path)
    ping_sleep = awaits_path.to.itself()
    start_moving = awaits_path.to(moving)
    dest_not_reached = moving.to.itself()
    dest_reached = moving.to(new_subtask)
    execute_actions = new_subtask.to(executing)
    execute_more = executing.to.itself()
    execute_done = executing.to(new_subtask)
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


class ConfiguredAgent(AgentFSM):
    hooks_api: AgentHooksAPI
    state_api: AgentStateAPI
    io_sub: Submitter
    state_sub: Submitter

    def __init__(
        self,
        hooks: AgentHooksAPI,
        state: AgentStateAPI,
        io_sub: Submitter,
        state_sub: Submitter,
    ) -> None:
        super().__init__()
        self.io_sub = io_sub
        self.state_sub = state_sub
        self.state_api = state
        self.hooks_api = hooks

    def do(self, tr: Callable[[], None]):
        self.state_sub.submit(tr)

    def schedule(self, hook: Callable[[], None]):
        self.io_sub.submit(hook)

    def on_enter_initial(self):
        log.debug("Agent done")

    def on_enter_idle(self):
        log.debug("looking for tasks")
        if self.state_api.more_tasks:
            log.debug("fetch next task")
            self.do(self.submit_task)
            return
        if self.state_api.error_found:
            self.do(self.got_error)
            return
        if self.state_api.must_stop:
            log.debug("Stops loop")
            self.do(self.stop)
            self.schedule(self.hooks_api.suspend)
            return
        log.debug("will sleep for a second while idle")
        self.do(self.ping_idle)
        self.schedule(self.hooks_api.listen_for_tasks)

    def on_enter_new_task(self):
        left = self.state_api.more_subtasks
        log.debug(f"{left} subtasks left")
        if left > 0:
            log.debug("submits dest reached check")
            self.do(self.submit_subtask)
            self.schedule(self.hooks_api.next_subtask)
            self.schedule(self.hooks_api.check_dest_reached)
            return
        log.debug("task completed")
        self.do(self.done_task)
        self.schedule(self.hooks_api.next_task)

    def on_enter_new_subtask(self):
        if not self.state_api.dest_reached:
            log.debug("looks for a next chuck")
            self.do(self.wait_for_path)
            self.schedule(self.hooks_api.fetch_next_chunk)
            return
        if self.state_api.more_exec_actions:
            log.debug("will execute actions")
            self.do(self.execute_actions)
            return
        log.debug("subtask completed")
        self.do(self.done_subtask)

    def on_enter_awaits_path(self):
        if self.state_api.path_found:
            # log.debug("will fetch move instructions")
            self.do(self.start_moving)
            return
        log.debug("pings for next chunk")
        self.do(self.ping_sleep)
        self.schedule(lambda: sleep(1))

    def on_enter_moving(self):
        if self.state_api.more_path_actions:
            log.debug("starts moving")
            self.do(self.dest_not_reached)
            self.schedule(self.hooks_api.send_move_action)
            return
        log.debug("current chunk sent, checks if reached dest")
        self.do(self.dest_reached)
        self.schedule(self.hooks_api.check_dest_reached)

    def on_enter_executing(self):
        left = self.state_api.more_exec_actions
        log.debug(f"{left} more exec left to do")
        if left > 0:
            # log.debug("will trigger action exec")
            self.do(self.execute_more)
            self.schedule(self.hooks_api.send_exec_action)
            return
        log.debug("done exec")
        self.do(self.execute_done)

    def on_enter_error(self):
        log.debug("error found")
