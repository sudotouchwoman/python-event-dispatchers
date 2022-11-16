# from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import threading
from time import sleep
from bot import WouldBlockError
from bot.state import AquiredStateError, StateManager, State


logging.basicConfig(
    format="[%(asctime)s]::[%(threadName)s] - %(message)s",
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
                goto_error = sleep_for % 2 == 1
                logging.debug(msg="Leaving context")
            if not goto_error:
                return
            logging.debug(msg="Tries to enter Error mode")
            with m(State.ERROR, blocking=blocking, timeout=timeout):
                logging.debug(msg="Entered Error mode")
                sleep(sleep_for)
                logging.debug(msg="Leaving Error mode")
        except AquiredStateError as e:
            logging.error(f"Error with context: {e}")
        except WouldBlockError as e:
            logging.error(f"Would have blocked: {e}")

    def thread_generator():
        yield lambda: goto_state(State.MOVING, 3)
        yield lambda: goto_state(State.MOVING, 5, blocking=False)
        yield lambda: goto_state(State.IDLE, 5, blocking=False)
        yield lambda: goto_state(State.BUSY, 5, 7)
        yield lambda: goto_state(State.IDLE, 2, blocking=False)

    for t in map(
        lambda name, target: threading.Thread(target=target, name=name),
        "ABCDE",
        thread_generator(),
    ):
        t.start()
        sleep(0.5)

    # m.run_until_complete()
    # threading.Thread(
    #     name="A",
    #     target=lambda: goto_state(State.MOVING, 3),
    # ).start()
    # threading.Thread(
    #     name="B",
    #     target=lambda: goto_state(State.MOVING, 5, blocking=False),
    # ).start()
    # threading.Thread(
    #     name="C",
    #     target=lambda: goto_state(State.IDLE, 5, blocking=False),
    # ).start()
    # threading.Thread(
    #     name="E",
    #     target=lambda: goto_state(State.BUSY, 5, 7),
    # ).start()
    # sleep(8)
    # threading.Thread(
    #     name="D",
    #     target=lambda: goto_state(State.IDLE, 2, blocking=False),
    # ).start()
    # with ThreadPoolExecutor() as executor:
    #     futures = []
    #     for f in thread_generator():
    #         futures.append(executor.submit(f))
    #     for _ in as_completed(futures):
    #         pass
    # threading.Thread(
    #     name="A",
    #     target=lambda: goto_state(State.MOVING, 3),
    # ).start()
    # threading.Thread(
    #     name="B",
    #     target=lambda: goto_state(State.MOVING, 5, blocking=False),
    # ).start()
    # threading.Thread(
    #     name="C",
    #     target=lambda: goto_state(State.IDLE, 5, blocking=False),
    # ).start()
    # threading.Thread(
    #     name="E",
    #     target=lambda: goto_state(State.BUSY, 5, 7),
    # ).start()
    # sleep(8)
    # threading.Thread(
    #     name="D",
    #     target=lambda: goto_state(State.IDLE, 2, blocking=False),
    # ).start()


if __name__ == "__main__":
    main()
