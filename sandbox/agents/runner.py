from enum import Enum, unique
import logging
from time import sleep
from typing import Callable
from statemachine import State, StateMachine

from .types import AgentAPI, Submitter

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
    do_action = new_subtask.to(executing) | executing.to.itself()
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
    api: AgentAPI
    io_sub: Submitter
    state_sub: Submitter

    def __init__(
        self, api: AgentAPI, io_sub: Submitter, state_sub: Submitter
    ) -> None:
        super().__init__()
        self.io_sub = io_sub
        self.state_sub = state_sub
        self.api = api

    def wants_state(self, tr: Callable[[], None]):
        self.state_sub.submit(tr)

    def wants_run(self, hook: Callable[[], None]):
        self.io_sub.submit(hook)

    def on_enter_initial(self):
        logging.debug("Agent done")

    def on_start(self):
        logging.debug("Starts operation")
        self.wants_run(self.api.listen_for_tasks)

    def on_enter_idle(self):
        logging.debug("idle")
        if self.api.more_tasks:
            self.wants_state(self.submit_task)
            return
        self.wants_state(self.ping_idle)

    def on_submit_task(self):
        logging.debug("fetch next subtask from tuple")
        self.wants_run(self.api.next_subtask)

    def on_ping_idle(self):
        logging.debug("will sleep for a second while idle")
        self.wants_run(lambda: sleep(1))

    def on_enter_new_task(self):
        logging.debug("new task")
        if self.api.more_subtasks:
            self.wants_state(self.submit_subtask)
            return
        self.wants_state(self.done_task)

    def on_submit_subtask(self):
        logging.debug("submits dest reached check")
        self.wants_run(self.api.check_dest_reached)

    def on_enter_new_subtask(self):
        logging.debug("new subtask")
        if not self.api.dest_reached:
            self.wants_state(self.wait_for_path)
            return
        if self.api.more_exec_actions:
            self.wants_state(self.do_action)
            return
        self.wants_state(self.done_subtask)

    def on_wait_for_path(self):
        logging.debug("looks for a next chuck")
        self.wants_run(self.api.next_chunk)

    def on_enter_awaits_path(self):
        logging.debug("pings for next chunk")
        if self.api.path_found:
            self.wants_state(self.got_path)
            return
        self.wants_state(self.ping_sleep)

    def on_ping_sleep(self):
        logging.debug("sleeps before next ping")
        self.wants_run(lambda: sleep(1))

    def on_got_path(self):
        logging.debug("will fetch move instructions")
        self.wants_run(self.api.send_move_action)

    def on_enter_moving(self):
        logging.debug("starts moving")
        if self.api.more_path_actions:
            self.wants_state(self.dest_not_reached)
            return
        self.wants_state(self.dest_reached)

    def on_dest_not_reached(self):
        logging.debug("will send another move instruction")
        self.wants_run(self.api.send_move_action)

    def on_dest_reached(self):
        logging.debug("current chunk sent, checks if reached dest")
        self.wants_run(self.api.check_dest_reached)

    def on_enter_executing(self):
        logging.debug("execution stage")
        if self.api.more_exec_actions:
            self.wants_state(self.do_action)
            return
        self.wants_state(self.done_action)

    def on_do_action(self):
        logging.debug("will trigger action exec")
        self.wants_run(self.api.send_exec_action)

    def on_done_action(self):
        logging.debug("all actions done")

    def on_subtask_done(self):
        logging.debug("subtask completed")
        self.wants_run(self.api.next_subtask)

    def on_task_done(self):
        logging.debug("task done")

    def on_enter_error(self):
        logging.debug("error found")
