from contextlib import contextmanager
from enum import Enum
import logging
import threading
from typing import Iterator

from . import RWLock, nonblock_guard


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


class RequestCancel:
    __lock: threading.Lock
    __canceled: bool
    state: State

    def __init__(self, state: State) -> None:
        self.state = state
        self.__canceled = False
        self.__lock = threading.Lock()

    @property
    def canceled(self) -> bool:
        with self.__lock:
            return self.__canceled

    def cancel(self) -> None:
        with self.__lock:
            if self.__canceled:
                raise RuntimeError()
            self.__canceled = True
