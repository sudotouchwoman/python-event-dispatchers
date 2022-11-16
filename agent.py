# from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import threading
from time import sleep
from typing import Optional
from bot import WouldBlockError
from bot.state import AquiredStateError, State
from bot.transactions import StateReducer


logging.basicConfig(
    format="[%(asctime)s]::[%(threadName)s] - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG,
)


def main():
    m = StateReducer()

    def goto_state(
        s: State,
        sleep_for: float = 0,
        timeout: Optional[float] = None,
        blocking: bool = True,
    ):
        try:
            # attach is performed in a non-blocking manner
            # though will borrow the state if it does match
            # while mutate will try to perform a transaction
            accessor = (
                lambda: m.mutate(s, timeout=timeout)
                if blocking
                else m.attach(s)
            )
            with accessor():
                logging.debug(msg=f"In state {m.state}, holders: {m.holders}")
                sleep(sleep_for)
                logging.debug(msg="Leaving")
        except AquiredStateError as e:
            logging.error(f"Error with state: {e}")
        except WouldBlockError as e:
            logging.error(f"Would have blocked: {e}")

    def thread_generator():
        # blocking routines would try to mutate the state
        # while non-blocking would only try to peek
        yield lambda: goto_state(State.MOVING, 3)
        yield lambda: goto_state(State.MOVING, 5, blocking=False)
        yield lambda: goto_state(State.IDLE, 5, blocking=False)
        yield lambda: goto_state(State.BUSY, 5, 1)
        yield lambda: goto_state(State.IDLE, 2, blocking=False)
        yield lambda: goto_state(State.IDLE, 5)

    for t in map(
        lambda name, target: threading.Thread(target=target, name=name),
        "ABCDEF",
        thread_generator(),
    ):
        t.start()
        sleep(1)

    m.run_until_complete()


if __name__ == "__main__":
    main()
