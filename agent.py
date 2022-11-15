import logging
import threading
from time import sleep
from bot import WouldBlockError
from bot.state import StateManager, State


logging.basicConfig(
    format="[%(asctime)s]::[%(name)s]::[%(threadName)s] - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG,
)


def main():
    m = StateManager()

    def goto_state(s: State, timeout: float = 0):
        try:
            with m(s):
                logging.debug(msg=f"In state {m.state}, holders: {m.holders}")
                sleep(timeout)
                logging.debug(msg="Leaving context")
        except ValueError as e:
            logging.error(f"Error with context {e}")
        except WouldBlockError:
            logging.error("Would have blocked")

    threading.Thread(
        name="goto-A",
        target=lambda: goto_state(State.MOVING, 3),
    ).start()
    threading.Thread(
        name="goto-B",
        target=lambda: goto_state(State.MOVING, 5),
    ).start()
    threading.Thread(
        name="goto-C",
        target=lambda: goto_state(State.IDLE),
    ).start()
    sleep(8)
    threading.Thread(
        name="goto-D",
        target=lambda: goto_state(State.IDLE, 2),
    ).start()


if __name__ == "__main__":
    main()
