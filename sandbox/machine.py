from enum import Enum, unique
import logging
import queue
import threading
from time import sleep
from statemachine import State, StateMachine


logging.basicConfig(
    format="[%(asctime)s]::[%(threadName)s] - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG,
)


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


class ConfiguredAgent(AgentFSM):
    events: queue.Queue
    task: str

    def __init__(self, events: queue.Queue) -> None:
        super().__init__()
        self.events = events
        self.task = ""

    def new_job(self, job: str):
        self.events.put(job)

    def critical(self):
        self.events.put(States.ERROR)

    def resume(self):
        self.events.put(States.IDLE)

    def stop_agent(self):
        self.events.put(States.INITIAL)

    def on_enter_initial(self):
        logging.debug("Agent done")

    def on_exit_initial(self):
        logging.debug("Starts operation")

    def on_enter_idle(self):
        logging.debug("idle")
        event = self.events.get()
        self.events.task_done()
        logging.debug(f"woke up: {event}")
        if event == States.ERROR:
            self.got_error()
            return
        if event == States.INITIAL:
            self.stop()
            return
        self.task = event
        self.submit_task()

    def on_enter_new_task(self):
        logging.debug(f"new task: {self.task}")
        sleep(3)
        logging.debug("task done")
        self.go_idle()

    def on_enter_error(self):
        logging.debug("error found")
        for event in iter(self.events.get, States.IDLE):
            self.events.task_done()
            logging.debug(f"suppressed: {event}")
        logging.debug("recovered")
        self.recover()


def main():
    q = queue.Queue(maxsize=3)
    fsm = ConfiguredAgent(q)

    # def make_jobs():
    #     fsm.new_job("some-job")
    #     fsm.new_job("another-job")
    #     fsm.critical()
    #     fsm.new_job("ping-job")
    #     fsm.new_job("ping-job")

    # threading.Thread(name="A", target=make_jobs, daemon=False).start()
    # fsm.start()
    threading.Thread(name="A", target=fsm.start, daemon=False).start()

    fsm.new_job("some-job")
    fsm.new_job("another-job")
    fsm.critical()
    fsm.new_job("ping-job")
    fsm.new_job("ping-job")
    fsm.resume()
    fsm.stop_agent()


if __name__ == "__main__":
    main()
