from contextlib import contextmanager
from enum import Enum
import threading
from typing import Iterator

from . import nonblock_guard


class State(Enum):
    IDLE = 1
    MOVING = 2
    BUSY = 3
    ERROR = 4


class StateManager:
    __context_lock: threading.RLock
    __mission_lock: threading.Lock
    __holders_lock: threading.Lock
    __current_state: State
    __context_holders: int

    def __init__(self, initial_state: State = State.IDLE) -> None:
        self.__mission_lock = threading.Lock()
        self.__holders_lock = threading.Lock()
        self.__context_lock = threading.RLock()
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
                raise ValueError(f"{holders} consumers use {current_state}")

    def __clear_state(self) -> None:
        with self.__holders_lock:
            if self.__context_holders > 0:
                return
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
    def __call__(self, state: State, timeout: float = -1) -> Iterator[None]:
        # interface for state mutations
        # ensures that code inside this context
        # runs in correct state
        if self.__current_state == state:
            self.__add_holder()
            try:
                yield
            finally:
                self.__drop_holder()
                self.__clear_state()
            return
        # modify the state...
        with nonblock_guard(self.__context_lock, timeout):
            # check if we can go to this state
            self.__ensure_context_change(state)
            self.__reset_holders()
            self.__current_state = state
        try:
            yield
        finally:
            self.__drop_holder()
            self.__clear_state()
