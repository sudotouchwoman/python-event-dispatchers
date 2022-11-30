from typing import Callable, List
import pytest

from agents.machine import AgentFSM

T = List[Callable[[AgentFSM], None]]


@pytest.fixture
def subtask_move_loop() -> T:
    return [
        lambda x: x.wait_for_path(),
        *[lambda x: x.ping_sleep()] * 2,
        lambda x: x.start_moving(),
        lambda x: x.dest_not_reached(),
        lambda x: x.dest_reached(),
    ]


@pytest.fixture
def subtask_loop(subtask_move_loop: T) -> T:
    return [
        lambda x: x.submit_subtask(),
        *subtask_move_loop,
        lambda x: x.execute_actions(),
        *[lambda x: x.execute_more()] * 2,
        lambda x: x.execute_done(),
        lambda x: x.done_subtask(),
    ]


@pytest.fixture
def task_loop(subtask_loop: T) -> T:
    return [
        lambda x: x.submit_task(),
        *subtask_loop,
        *subtask_loop,
        lambda x: x.done_task(),
    ]


@pytest.fixture
def complete_valid_state_loop(task_loop: T) -> T:
    return [
        lambda x: x.start(),
        lambda x: x.ping_idle(),
        *task_loop,
        *task_loop,
        lambda x: x.got_error(),
        lambda x: x.recover(),
        *task_loop,
        lambda x: x.stop(),
    ]


def test_machine_loop(complete_valid_state_loop: T):
    machine = AgentFSM()
    for transit in complete_valid_state_loop:
        transit(machine)
    assert machine.is_initial is True  # type: ignore
