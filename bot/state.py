from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from enum import Enum
from functools import reduce
import logging
import queue
import threading
from typing import Iterator, Optional

from . import RWLock, WouldBlockError, nonblock_guard


class AquiredStateError(ValueError):
    pass


class State(Enum):
    IDLE = 1
    MOVING = 2
    BUSY = 3
    ERROR = 4


class StateManager:
    __context_lock: RWLock
    __mission_lock: threading.Lock
    __holders_lock: threading.Lock
    __current_state: State
    __context_holders: int

    def __init__(self, initial_state: State = State.IDLE) -> None:
        self.__mission_lock = threading.Lock()
        self.__holders_lock = threading.Lock()
        self.__context_lock = RWLock()
        self.__context_holders = 0
        self.__current_state = initial_state

    @property
    def state(self) -> State:
        return self.__current_state

    @property
    def holders(self) -> int:
        with self.__holders_lock:
            return self.__context_holders

    def __ensure_context_change(self, state: State) -> None:
        # check if we can switch current state
        # to a new one here
        with self.__holders_lock:
            if self.__context_holders > 0:
                holders, current_state = (
                    self.__context_holders,
                    self.__current_state,
                )
                raise AquiredStateError(
                    f"{holders} consumers use {current_state} (not {state})"
                )
            if self.__current_state == State.ERROR and state != State.ERROR:
                raise AquiredStateError("error mode is final")
            self.__current_state = state
            logging.debug(msg=f"{state}")

    def __clear_state(self) -> None:
        with self.__holders_lock:
            if self.__context_holders > 0:
                logging.debug(msg="still being held, nothing to do")
                return
        logging.debug(msg="cleans up the context")
        # may involve more complicated logic
        return

    def __add_holder(self):
        with self.__holders_lock:
            self.__context_holders += 1

    def __drop_holder(self):
        with self.__holders_lock:
            self.__context_holders -= 1

    def __reset_holders(self):
        with self.__holders_lock:
            self.__context_holders = 1

    @property
    def mission(self):
        # ensures that missions are run atomically
        return nonblock_guard(self.__mission_lock)

    @contextmanager
    def attach(
        self,
        state: State,
        blocking: bool = True,
        timeout: float = -1,
    ) -> Iterator[None]:
        # interface for state mutations
        # ensures that code inside this context
        # runs in correct state
        with self.__context_lock.read(blocking=blocking, timeout=timeout):
            if self.__current_state == state:
                self.__add_holder()
                try:
                    yield
                finally:
                    self.__drop_holder()
                    self.__clear_state()
                return
            raise AquiredStateError("can only attech to existing context")

    @contextmanager
    def mutate(
        self,
        state: State,
        blocking: bool = True,
        timeout: float = -1,
    ) -> Iterator[None]:
        # interface for state mutations
        # ensures that code inside this context
        # runs in correct state
        with self.__context_lock.read(blocking=blocking, timeout=timeout):
            if self.__current_state == state:
                self.__add_holder()
                try:
                    yield
                finally:
                    self.__drop_holder()
                    self.__clear_state()
                return
        # modify the state...
        logging.debug(msg="tries to mutate context")
        with nonblock_guard(self.__context_lock, blocking, timeout):
            # check if we can go to this state
            self.__ensure_context_change(state)
            self.__reset_holders()
        with self.__context_lock.read(blocking=blocking, timeout=timeout):
            try:
                yield
            finally:
                self.__drop_holder()
                self.__clear_state()


class AtomicCounter:
    def __init__(self, initial_value: int = 0) -> None:
        self.val = initial_value
        self.lock = threading.RLock()

    def inc(self, value: int = 1) -> None:
        with self.lock:
            self.val += value

    def dec(self, value: int = 1) -> None:
        with self.lock:
            self.val -= value

    @property
    def value(self) -> int:
        with self.lock:
            return self.val


class StateReducer:
    requests: queue.Queue[Optional[State]]
    # requests: queue.Queue[Optional[Tuple[State, Future[None]]]]
    closers: queue.Queue[State]
    confirms: queue.Queue[bool]
    current_state: State
    holders_cnt: AtomicCounter

    def __init__(self, initial_state: State = State.IDLE) -> None:
        self.holders_cnt = AtomicCounter()

        self.closers = queue.Queue()
        self.futures = queue.Queue()

        self.requests = queue.Queue(maxsize=1)
        self.confirms = queue.Queue(maxsize=1)
        self.current_state = initial_state
        self.pool = ThreadPoolExecutor()
        self.pool.submit(self.transaction_dispatcher)

    @property
    def state(self) -> State:
        return self.current_state

    @state.setter
    def state(self, state: State) -> None:
        logging.debug(msg=f"New: {state}")
        self.current_state = state

    @property
    def holders(self) -> int:
        return self.holders_cnt.value

    def run_until_complete(self):
        self.requests.put(None)
        self.confirms.put(False)

    # def transaction_dispatcher(self):
    #     for s in iter(self.requests.get, None):
    #         self.requests.task_done()
    #         logging.debug(msg=f"Request: {s}")
    #         if self.holders == 0:
    #             self.state = s
    #         if s == self.state:
    #             # OK, we are already in this state
    #             self.holders_cnt.inc()
    #             self.closers.put(s)
    #             self.confirms.put(True)
    #             continue
    #         # at this moment, caller could have
    #         # already timed out
    #         # here, one should check whether the
    #         # last request timed out
    #         # business-specific logic for state setting
    #         self.closers.join()
    #         self.state = s
    #         self.holders_cnt.inc()
    #         self.closers.put(s)
    #         self.confirms.put(True)

    def transaction_dispatcher(self):
        reduce(self.reducer, iter(self.requests.get, None), None)
        logging.debug(msg="Dispatcher done")

    def reducer(self, prev: Optional[State], current: State) -> State:
        logging.debug(msg=f"{prev}->{current}")
        if prev == current:
            logging.debug(msg="Nothing to reduce")
            self.closers.put(current)
            self.holders_cnt.inc()
            self.confirms.put(True)
            return current

        if prev is not None and prev != current:
            logging.debug(msg="Waits for context release")
            self.closers.join()
            logging.debug(msg="Context released")

        self.holders_cnt.inc()
        self.closers.put(current)
        self.confirms.put(True)
        self.state = current
        return current

    @contextmanager
    def __call__(
        self,
        state: State,
        blocking: bool = True,
        timeout: float = 0.0,
    ):
        logging.debug(msg=f"Needs: {state}")
        try:
            self.requests.put(state, block=blocking, timeout=timeout)
            confirmation = self.confirms.get(block=blocking, timeout=timeout)
            self.confirms.task_done()
            if not confirmation:
                raise AquiredStateError(
                    f"unreachable state: {self.state} (want {state})"
                )
        except queue.Empty:
            raise WouldBlockError(f"empty exc: {self.state} (want {state})")
        except queue.Full:
            raise WouldBlockError(f"full exc: {self.state} (want {state})")
        try:
            logging.debug(msg=f"Aquired resources ({self.holders})")
            yield
        finally:
            self.closers.get()
            self.closers.task_done()
            self.holders_cnt.dec()
            logging.debug(msg=f"Released resources ({self.holders} left)")
