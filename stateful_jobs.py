import random
from threaded.dispatcher import dummy_producer
from threaded.jobs import SimpleJob, Pipeline


def main() -> None:

    random.seed(42)

    api = Pipeline()

    for i, p in enumerate(dummy_producer()):
        api.schedule(SimpleJob(f"job-{i}", p))

    # in this example, jobs are produced from a fixed-size
    # generator and then can possibly re-schedule themselves into the loop
    # thus this prompt is put here, not that in a real
    # app, one is either likely to run this
    # in a =n infinite loop or kill without caring
    input("Press Enter to stop...\n")
    api.run_until_complete()


if __name__ == "__main__":
    main()
