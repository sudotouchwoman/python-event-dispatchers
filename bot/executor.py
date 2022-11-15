from contextlib import contextmanager
from typing import Any, Iterator

from .state import StateManager, State
from .mqtt import MqttClient


class AgentExecutor:
    __client: MqttClient
    __state: StateManager

    @contextmanager
    def client(self) -> Iterator[MqttClient]:
        with self.__state(State.BUSY):
            yield self.__client

    def reach_destination(self, dest: Any) -> None:
        # probably communicate with external component here
        with self.__state(State.MOVING):
            # network communication, etc
            pass
