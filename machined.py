import logging
import threading
from time import sleep
from machine.states import (
    ActionDispatcher,
    TransitionDispatcher,
    AgentFSM,
    States,
)

logging.basicConfig(
    format="[%(asctime)s]::[%(threadName)s] - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG,
)


def chatty_timer(time: float, name: str = ""):
    logging.debug(f"{name} will sleep for {time}")
    sleep(time)
    return time


def main():
    action_manager = ActionDispatcher()
    submitter = action_manager.submitter
    dispatcher = TransitionDispatcher(action_manager, max_requests=3)
    sender = dispatcher.sender

    def run_four_tasks():
        finished_tasks = 0

        def new_task_hook():
            nonlocal finished_tasks
            if finished_tasks > 4:
                logging.info("All tasks done")
                dispatcher.stop()
                return
            logging.debug(f"Got new task ({finished_tasks})")
            finished_tasks += 1
            submitter(lambda: chatty_timer(1, "new-task"))
            logging.debug("Submitted new task")
            sender("go_idle")

        return new_task_hook

    def task_done_hook():
        logging.debug("Going idle")
        submitter(lambda: chatty_timer(2, "task-done"))
        logging.debug("Submitted chatter task")
        sender("submit_task")

    state_hooks = {
        States.IDLE: task_done_hook,
        States.GOT_TASK: run_four_tasks(),
    }

    agent = AgentFSM(state_hooks=state_hooks)
    dispatcher.agent = agent

    threading.Thread(
        name="event-dispatcher",
        target=dispatcher.dispatch,
        daemon=False,
    ).start()

    dispatcher.sender("submit_task")
    # print(f"Agent: {agent.current_state}")
    # agent.submit_task()
    # agent.submit_subtask()
    # agent.wait_for_path()


if __name__ == "__main__":
    main()
