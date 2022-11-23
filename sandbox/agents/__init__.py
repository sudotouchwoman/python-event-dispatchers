import logging


logging.basicConfig(
    format="[%(asctime)s]::[%(threadName)s] - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG,
)
