from enum import Enum, unique
import logging


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    fmt="[%(asctime)s]::[%(name)s]::[%(threadName)s] - %(message)s",
    datefmt="%H:%M:%S",
)
handler.setFormatter(formatter)
log.addHandler(handler)


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
