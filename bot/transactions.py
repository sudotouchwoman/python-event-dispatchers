from contextlib import contextmanager
from functools import reduce
import logging
import queue
import threading
from typing import Optional

from .state import AquiredStateError, RequestCancel, State, AtomicCounter


class StateReducer:
    def __init__(self, initial_state: State = State.IDLE) -> None:
        self.holders_cnt = AtomicCounter()
        self.state_lock = threading.RLock()

        self.processed = queue.Queue()
        self.pending = queue.Queue()
        self.done = queue.Queue()

        self.current_state = initial_state
        threading.Thread(
            target=self.transaction_dispatcher,
            name="dispatcher",
        ).start()

    @property
    def state(self) -> State:
        with self.state_lock:
            return self.current_state

    @state.setter
    def state(self, state: State) -> None:
        with self.state_lock:
            if self.current_state == state:
                logging.debug(f"Still {state.name}")
                self.holders_cnt.inc()
                return
            logging.debug(msg=f"{state.name}")
            self.current_state = state

    @property
    def holders(self) -> int:
        return self.holders_cnt.value

    def run_until_complete(self):
        self.pending.put(None)

    def transaction_dispatcher(self):
        def reducer(prev: State, req: RequestCancel) -> State:
            self.pending.task_done()
            logging.debug(msg=f"{prev.name} => {req.state.name}")
            if req.canceled:
                logging.debug("Request timed out")
                return prev
            # if state was asked to change
            if prev == req.state:
                logging.debug("Nothing to reduce")
                return prev
            logging.debug("Waits for release")
            # block until all holders of current state were
            # released
            self.done.join()
            logging.debug("All done")
            # check once again
            if req.canceled:
                logging.debug("Request timed out during wait")
                return prev
            # custom logic here
            self.state = req.state
            self.processed.put_nowait(self.state)
            return req.state

        logging.debug("Starts dispatcher")
        reduce(
            reducer,
            iter(self.pending.get, None),
            # filter(lambda r: not r.canceled, iter(self.pending.get, None)),
            self.current_state,
        )
        logging.debug(msg="Dispatcher done")

    @contextmanager
    def attach(
        self,
        state: State,
    ):
        logging.debug(msg=f"Want {state.name} (attach)")
        holds_state = False
        with self.state_lock:
            if not self.state == state:
                raise AquiredStateError("can't attach")
            self.pending.put_nowait(RequestCancel(state))
            self.holders_cnt.inc()
            self.done.put_nowait(None)
            holds_state = True
            logging.debug("Attached to current state")
        try:
            yield
        finally:
            logging.debug("Released context")
            if not holds_state:
                return
            self.done.get_nowait()
            self.done.task_done()
            self.holders_cnt.dec()

    @contextmanager
    def mutate(
        self,
        state: State,
        timeout: Optional[float] = None,
    ):
        logging.debug(msg=f"Want {state.name} {timeout=} (mutate)")
        request = RequestCancel(state=state)
        holds_state = False
        try:
            self.pending.put_nowait(request)
            logging.debug(msg="Made request")
            p = self.processed.get(timeout=timeout)
            self.processed.task_done()
            if p != state:
                raise AquiredStateError(f"want {state}, just got {p}")
            logging.debug(msg=f"Confirmed: {p}")
            self.holders_cnt.inc()
            self.done.put_nowait(None)
            holds_state = True
        except queue.Empty:
            logging.warning("get timed out")
            request.cancel()
            raise AquiredStateError(f"want {state}, got {self.state}")
        except Exception as e:
            logging.error(e)
            raise e
        try:
            yield
        finally:
            logging.debug("Released context")
            if not holds_state:
                return
            self.done.get_nowait()
            self.done.task_done()
            self.holders_cnt.dec()
