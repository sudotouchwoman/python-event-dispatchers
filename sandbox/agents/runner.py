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
    got_path = awaits_path.to(moving)
    dest_not_reached = moving.to.itself()
    dest_reached = moving.to(new_subtask)
    do_exec_actions = new_subtask.to(executing)
    do_action = executing.to.itself()
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

    def wants_state(self, tr: Callable[[], None]):
        self.state_sub.submit(tr)

    def wants_run(self, hook: Callable[[], None]):
        self.io_sub.submit(hook)

    def on_enter_initial(self):
        log.debug("Agent done")

    def on_start(self):
        log.debug("Starts operation")
        self.wants_run(self.hooks_api.listen_for_tasks)

    def on_stop(self):
        log.debug("Stops loop")
        self.wants_run(self.hooks_api.suspend)

    def on_enter_idle(self):
        log.debug("idle")
        if self.state_api.more_tasks:
            self.wants_state(self.submit_task)
            return
        if self.state_api.error_found:
            self.wants_state(self.got_error)
            return
        if self.state_api.must_stop:
            self.wants_state(self.stop)
            return
        self.wants_state(self.ping_idle)

    def on_submit_task(self):
        log.debug("fetch next subtask from tuple")
        self.wants_run(self.hooks_api.next_subtask)

    def on_ping_idle(self):
        log.debug("will sleep for a second while idle")
        self.wants_run(lambda: sleep(1))
        self.wants_run(self.hooks_api.listen_for_tasks)

    def on_enter_new_task(self):
        log.debug("new task")
        if self.state_api.more_subtasks:
            self.wants_state(self.submit_subtask)
            return
        self.wants_state(self.done_task)

    def on_submit_subtask(self):
        log.debug("submits dest reached check")
        self.wants_run(self.hooks_api.check_dest_reached)

    def on_enter_new_subtask(self):
        log.debug("new subtask")
        if not self.state_api.dest_reached:
            self.wants_state(self.wait_for_path)
            return
        if self.state_api.more_exec_actions:
            self.wants_state(self.do_exec_actions)
            return
        log.debug("done subtask")
        self.wants_state(self.done_subtask)

    def on_wait_for_path(self):
        log.debug("looks for a next chuck")
        self.wants_run(self.hooks_api.next_chunk)

    def on_enter_awaits_path(self):
        log.debug("pings for next chunk")
        if self.state_api.path_found:
            self.wants_state(self.got_path)
            return
        self.wants_state(self.ping_sleep)

    def on_ping_sleep(self):
        log.debug("sleeps before next ping")
        self.wants_run(lambda: sleep(1))

    def on_got_path(self):
        log.debug("will fetch move instructions")
        self.wants_run(self.hooks_api.send_move_action)

    def on_enter_moving(self):
        log.debug("starts moving")
        if self.state_api.more_path_actions:
            self.wants_state(self.dest_not_reached)
            return
        self.wants_state(self.dest_reached)

    def on_dest_not_reached(self):
        log.debug("will send another move instruction")
        self.wants_run(self.hooks_api.send_move_action)

    def on_dest_reached(self):
        log.debug("current chunk sent, checks if reached dest")
        self.wants_run(self.hooks_api.check_dest_reached)

    def on_enter_executing(self):
        log.debug("execution stage")
        more_exec_actions = self.state_api.more_exec_actions
        log.debug(f"{more_exec_actions} more to do")
        if more_exec_actions > 0:
            self.wants_state(self.do_action)
            return
        log.debug("done exec")
        self.wants_state(self.done_action)

    def on_do_exec_actions(self):
        log.debug("will execute actions")

    def on_do_action(self):
        log.debug("will trigger action exec")
        self.wants_run(self.hooks_api.send_exec_action)

    def on_done_action(self):
        log.debug("all actions done")

    def on_subtask_done(self):
        log.debug("subtask completed")
        self.wants_run(self.hooks_api.next_subtask)

    def on_task_done(self):
        log.debug("task done")

    def on_enter_error(self):
        log.debug("error found")
