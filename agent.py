import logging
import threading
from time import sleep
from bot import WouldBlockError
from bot.state import AquiredStateError, StateManager, State


logging.basicConfig(
    format="[%(asctime)s]::[%(name)s]::[%(threadName)s] - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG,
)


def main():
    m = StateManager()

    def goto_state(
        s: State,
        sleep_for: float = 0,
        timeout: float = -1,
        blocking: bool = True,
    ):
        try:
            with m(s, blocking=blocking, timeout=timeout):
                logging.debug(msg=f"In state {m.state}, holders: {m.holders}")
                sleep(sleep_for)
                goto_error = False
                logging.debug(msg="Leaving context")
            if not goto_error:
                return
            with m(State.ERROR, blocking=blocking, timeout=timeout):
                logging.debug(msg="Entered Error mode")
                sleep(sleep_for)
                logging.debug(msg="Leaving Error mode")
        except AquiredStateError as e:
            logging.error(f"Error with context: {e}")
        except WouldBlockError:
            logging.error("Would have blocked")

    threading.Thread(
        name="goto-A",
        target=lambda: goto_state(State.MOVING, 3),
    ).start()
    threading.Thread(
        name="goto-B",
        target=lambda: goto_state(State.MOVING, 5, blocking=False),
    ).start()
    threading.Thread(
        name="goto-C",
        target=lambda: goto_state(State.IDLE, 5, blocking=False),
    ).start()
    threading.Thread(
        name="goto-E",
        target=lambda: goto_state(State.BUSY, 5, 6),
    ).start()
    sleep(8)
    threading.Thread(
        name="goto-D",
        target=lambda: goto_state(State.IDLE, 2, blocking=False),
    ).start()


if __name__ == "__main__":
    main()
