from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Callable, Iterable

from .mqtt import MqttClient
from . import WouldBlockError
from .state import StateManager
from .executor import AgentExecutor


class ActionType(Enum):
    # AisleCmd, CsCmd, etc
    pass


class MissionType(Enum):
    # guess we will have to come up with these
    # ourselves
    pass


class Task:
    destination: Any
    action: ActionType
    context: Any

    def send_to(self, mqtt_client: MqttClient) -> bool:
        # overriden by derived classes
        return False

    def execute_with(self, executor: AgentExecutor) -> bool:
        # overriden by derived classes
        return False

    def cleanup(self, executor: AgentExecutor) -> None:
        # if there are some steps to perform
        # as a disaster recovery, do it here
        pass


class Mission:
    def steps(self) -> Iterable[Task]:
        # overriden by derived classes
        return ()


class Sequencer:
    def mission_factory(self, m: MissionType, context: Any) -> Mission:
        return Mission()


class AgentAPI:
    executor: AgentExecutor
    state: StateManager
    sequencer: Sequencer
    exc_handle: Callable[[Exception], None]
    pool: ThreadPoolExecutor

    def can_run_now(self, t: Task) -> bool:
        # check if this task can be run along
        # with current task(s)
        return False

    def submit(self, t: Task) -> bool:
        # puts the task routine into the executor context
        # if possible
        if not self.can_run_now(t):
            return False
        # ok, submit to execution
        f = self.pool.submit(lambda: t.execute_with(self.executor))
        return f.result()

    def start_mission(self, m: MissionType, ctx: Any) -> bool:
        mission = self.sequencer.mission_factory(m, ctx)
        # aquire the mission lock here
        try:
            with self.state.mission:
                for step in mission.steps():
                    err = self.submit(step)
                    if not err:
                        continue
                    self.exc_handle(RuntimeError(err))
                    step.cleanup(self.executor)
                return True
        except WouldBlockError as e:
            self.exc_handle(e)
            return False
