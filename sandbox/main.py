import threading
from time import sleep
from agents.machine import ConfiguredAgent
from testing.mock_agent import Locations, MockAgent, SubTask, Task
from agents.dispatcher import AgentLoop


def main():
    loop = AgentLoop()
    mock_agent = MockAgent(loop)
    fsm = ConfiguredAgent(
        mock_agent,
        mock_agent,
        loop.io_submitter,
        loop.state_submitter,
    )

    def do_some_tasks():
        loop.state_submitter.submit(fsm.start)
        mock_agent.submit(
            Task(
                [
                    SubTask(Locations.LEVEL2, ["pick-up", "ping-base"]),
                    SubTask(Locations.BASE, ["do-this", "do-that"]),
                ]
            )
        )
        sleep(10)
        mock_agent.submit(
            Task(
                [
                    SubTask(
                        Locations.BASE,
                        ["open-door", "pick", "close-door", "ping-base"],
                    ),
                    SubTask(
                        Locations.LEVEL2, ["pick-up", "ping-base", "put-down"]
                    ),
                ]
            )
        )
        sleep(60)
        mock_agent.suspend()

    threading.Thread(target=do_some_tasks, name="user", daemon=True).start()
    loop.loop()


if __name__ == "__main__":
    main()
