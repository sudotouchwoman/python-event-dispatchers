import logging
from time import sleep
from typing import Callable
from statemachine import State, StateMachine

from . import States
from .types import AgentAction, AgentState, Submitter


# FA initiates io-bound tasks, but does not block
# inside states
# once entered a state, FA decides on a new transition
# once transition is complete, runner blocks on io-bound tasks
# after all io-bound tasks are completed, a new state is picked from
# the queue


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
    """State machine configured with callbacks and
    additional attributes.
    """

    actions_api: AgentAction
    state_api: AgentState
    io_sub: Submitter
    state_sub: Submitter

    def __init__(
        self,
        hooks: AgentAction,
        state: AgentState,
        io_sub: Submitter,
        state_sub: Submitter,
    ) -> None:
        super().__init__()
        self.io_sub = io_sub
        self.state_sub = state_sub
        self.state_api = state
        self.actions_api = hooks
        self.log = logging.getLogger(__name__)

    def transit_state(self, tr: Callable[[], None]):
        """Shorthand method for submitting state.

        Args:
            tr (Callable[[], None]): valid state transition
            method of parent state machine
        """
        self.state_sub.submit(tr)

    def do_action(self, action: Callable[[], None]):
        """Shorthand method for submitting actions.

        Args:
            tr (Callable[[], None]): valid action
            method of action API or just a callback
        """
        self.io_sub.submit(action)

    def on_enter_initial(self):
        self.log.debug("Agent done")

    def on_enter_idle(self):
        self.log.debug("idle")
        if self.state_api.more_tasks:
            self.log.debug("fetch next task")
            self.transit_state(self.submit_task)
            return
        if self.state_api.error_found:
            self.transit_state(self.got_error)
            return
        if self.state_api.must_stop:
            self.log.debug("Stops loop")
            self.transit_state(self.stop)
            self.do_action(self.actions_api.suspend)
            return
        self.transit_state(self.ping_idle)
        self.do_action(self.actions_api.listen_for_tasks)

    def on_enter_new_task(self):
        left = self.state_api.more_subtasks
        self.log.debug(f"{left} subtasks left")
        if left > 0:
            self.log.debug("submits dest reached check")
            self.transit_state(self.submit_subtask)
            self.do_action(self.actions_api.next_subtask)
            self.do_action(self.actions_api.update_location)
            return
        self.log.debug("task completed")
        self.transit_state(self.done_task)
        self.do_action(self.actions_api.done_task)

    def on_enter_new_subtask(self):
        if not self.state_api.dest_reached:
            self.log.debug("looks for a next chuck")
            self.transit_state(self.wait_for_path)
            self.do_action(self.actions_api.fetch_next_chunk)
            return
        if self.state_api.more_exec_actions:
            self.log.debug("will execute actions")
            self.transit_state(self.execute_actions)
            return
        self.log.debug("subtask completed")
        self.transit_state(self.done_subtask)

    def on_enter_awaits_path(self):
        if self.state_api.path_found:
            # self.log.debug("will fetch move instructions")
            self.transit_state(self.start_moving)
            return
        self.log.debug("pings for next chunk")
        self.transit_state(self.ping_sleep)
        self.do_action(lambda: sleep(1))

    def on_enter_moving(self):
        if self.state_api.more_path_actions:
            self.log.debug("starts moving")
            self.transit_state(self.dest_not_reached)
            self.do_action(self.actions_api.send_move_action)
            return
        self.log.debug("current chunk sent, checks if reached dest")
        self.transit_state(self.dest_reached)
        self.do_action(self.actions_api.update_location)

    def on_enter_executing(self):
        left = self.state_api.more_exec_actions
        self.log.debug(f"{left} more exec left to do")
        if left > 0:
            # self.log.debug("will trigger action exec")
            self.transit_state(self.execute_more)
            self.do_action(self.actions_api.send_exec_action)
            return
        self.log.debug("done exec")
        self.transit_state(self.execute_done)

    def on_enter_error(self):
        self.log.debug("error found")
