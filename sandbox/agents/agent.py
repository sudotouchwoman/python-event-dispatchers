from dataclasses import dataclass
from enum import Enum, unique
import logging
import queue
from time import sleep
from typing import Callable, List, Optional

from .runner import States
from .types import AgentStateAPI, AgentHooksAPI, Submitter
from .dispatcher import Dispatcher


log = logging.getLogger(__name__)


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


class MockAgent(AgentStateAPI, AgentHooksAPI):
    __task_submits: queue.Queue
    __current_task: Optional[Task]
    __current_subtask: SubTask
    __path_actions: List[str]
    __location: Locations

    def __init__(self, loop: Dispatcher) -> None:
        super().__init__()
        self.must_stop = False
        self.error_found = False
        self.__location = Locations.BASE
        self.loop = loop
        self.__task_submits = queue.Queue(maxsize=5)
        self.__path_actions = []
        self.__current_subtask = SubTask(Locations.BASE, [])
        self.__current_task = None

    @property
    def more_tasks(self) -> bool:
        return self.__current_task is not None

    @property
    def more_subtasks(self) -> int:
        if self.__current_task is None:
            return 0
        return len(self.__current_task.subtasks)

    @property
    def more_exec_actions(self) -> int:
        return len(self.__current_subtask.commands)

    @property
    def more_path_actions(self) -> int:
        return len(self.__path_actions)

    @property
    def dest_reached(self) -> bool:
        return self.__location == self.__current_subtask.loc

    def next_chunk(self):
        log.info("fetches next chunk")
        sleep(0.5)
        # some fixed path actions
        self.__path_actions = ["cs", "aisle", "cs"]

    def next_subtask(self):
        log.info("gets next subtask")
        if self.__current_task is None:
            log.error("integrity error: no current task")
            return
        self.__current_subtask = self.__current_task.next()

    def listen_for_tasks(self):
        # blocks until some event occurs
        log.debug("listens for tasks")
        self.must_stop = False
        try:
            next_task = self.__task_submits.get_nowait()
            self.__task_submits.task_done()
        except queue.Empty:
            log.debug("no tasks so far")
            return
        log.debug(f"recieved task: {next_task}")
        if next_task is None:
            log.info("stop listen")
            self.must_stop = True
            return
        if next_task == States.ERROR:
            log.error("caught error")
            return
        self.__current_task = next_task

    def check_dest_reached(self):
        if self.__current_subtask.loc == self.__location:
            log.debug("dest reached")
            return
        log.debug("has to move...")

    def send_move_action(self):
        action = self.__path_actions.pop(0)
        log.debug(f"sends move action: {action}")
        sleep(2)
        # for now, just assume that we got to the
        # distination in one hop
        self.__location = self.__current_subtask.loc
        log.debug("sent exec")

    def send_exec_action(self):
        if not self.more_exec_actions:
            raise RuntimeError("no more actions")
        action = self.__current_subtask.commands.pop(0)
        log.debug(f"sends exec action: {action}")
        log.debug(f"left todo: {self.__current_subtask.commands}")
        sleep(1)
        log.debug("sent exec")

    def submit(self, t: Task):
        self.__task_submits.put(t)
        log.debug(f"submitted new task: {t}")


class AgentLoop(Dispatcher):
    class LoopSumbitter(Submitter):
        __q: queue.Queue

        def __init__(self, q: queue.Queue) -> None:
            self.__q = q

        def submit(self, hook: Callable[[], None]):
            self.__q.put(hook)

    def __init__(self) -> None:
        super().__init__()
        self.state_submitter = self.LoopSumbitter(self.state_requests)
        self.io_submitter = self.LoopSumbitter(self.io_requests)
