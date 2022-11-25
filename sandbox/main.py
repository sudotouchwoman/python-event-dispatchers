import threading
from agents.runner import ConfiguredAgent
from agents.agent import AgentLoop, Locations, MockAgent, SubTask, Task


def main():
    loop = AgentLoop()
    mock_agent = MockAgent(loop)
    threading.Thread(target=loop.loop, name="loop", daemon=False).start()
    fsm = ConfiguredAgent(
        mock_agent,
        mock_agent,
        loop.io_submitter,
        loop.state_submitter,
    )
    loop.state_submitter.submit(fsm.start)
    mock_agent.submit(Task(
        [
            SubTask(Locations.BASE, ["do-this", "do-that"]),
            SubTask(Locations.LEVEL2, ["pick-up", "ping-base"])
        ]
    ))


if __name__ == "__main__":
    main()
