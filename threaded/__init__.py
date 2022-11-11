import logging


logging.basicConfig(
    format="[%(asctime)s]::[%(name)s]::[%(threadName)s] - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG,
)
